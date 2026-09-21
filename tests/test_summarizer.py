"""Tests for mcp_core.summarizer — pure functions, no mocking needed.

WHY THESE EXIST
---------------
The summarizer truncates a >50-row table to first 50 + last 2 rows, and compensates by
emitting a `Totals (all N rows)` line summed across EVERY row. That aggregate is the whole
point for the takeoff — but two silent failure modes were found on 2026-09-18:

  1. The sum was gated on a keyword allow-list that did NOT contain the finishing
     vocabulary (plaster / paint / tile / skirting / screed / _m2 / _m3), so the exact
     columns a finishing takeoff is about were omitted from the totals line.
  2. The numeric test read `data[0]` ONLY, so a single blank first cell erased the
     aggregate entirely.

Both were SILENT: the output looked like a normal truncated table. A missing totals line is
not evidence that a table has no numeric columns — the inverse of the project's rule that a
matching TOTAL is not evidence its PARTS are right.
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_core.summarizer import (
    summarize, MAX_TABLE_ROWS, TABLE_TAIL_ROWS, SHOW_ALL_TABLE_THRESHOLD,
)

FINISHING_COLS = ["Room", "FloorFinish", "FloorArea_m2", "WallPlaster_m2", "WallPaint_m2",
                  "WallTile_m2", "CeilingPlaster_m2", "Skirting_m", "Screed_m3"]


def table(cols, n, first_row=None, title="T"):
    """A structured-output payload holding one table of `n` rows."""
    rows = []
    for i in range(n):
        r = {c: "1.5" for c in cols}
        r["Room"] = f"R{i}"
        if i == 0 and first_row:
            r.update(first_row)
        rows.append(r)
    return {"structuredOutput": [{"type": "table", "title": title, "data": rows}]}


def totals_line(out):
    for line in out.splitlines():
        if "Totals (all" in line:
            return line
    return ""


def has_any_totals(out):
    return bool(totals_line(out))


# ── A. regression guards: the behaviour that must NOT change ──────────────

class TestRegressionGuards:
    def test_small_table_is_not_truncated(self):
        out = summarize(table(["Room", "Area_m2"], SHOW_ALL_TABLE_THRESHOLD))
        assert "rows total" not in out
        assert "more rows not shown" not in out

    def test_small_table_has_no_totals_line(self):
        # <= threshold: everything is visible, so an aggregate would be redundant
        out = summarize(table(["Room", "Area_m2"], 10))
        assert not has_any_totals(out)

    def test_large_table_truncates_to_head_plus_tail(self):
        out = summarize(table(["Room", "Area_m2"], 60))
        assert "60 rows total" in out
        assert f"showing first {MAX_TABLE_ROWS} + last {TABLE_TAIL_ROWS}" in out
        assert f"{60 - MAX_TABLE_ROWS - TABLE_TAIL_ROWS} more rows not shown" in out

    def test_totals_cover_all_rows_not_just_visible_ones(self):
        out = summarize(table(["Room", "Area_m2"], 60))   # 60 x 1.5 = 90
        assert "Totals (all 60 rows)" in out
        assert "90" in totals_line(out)

    def test_identifier_and_dimension_columns_are_never_summed(self):
        # This is WHY the allow-list exists: summing Id/Elevation is meaningless.
        cols = ["Id", "ElementId", "Level", "Elevation", "Area_m2"]
        out = summarize(table(cols, 60))
        t = totals_line(out)
        assert "Area_m2" in t
        for bad in ("Id:", "ElementId:", "Level:", "Elevation:"):
            assert bad not in t, f"{bad} must never be summed"

    def test_text_output_is_capped(self):
        payload = {"structuredOutput": [], "output": "\n".join(f"line {i}" for i in range(50))}
        out = summarize(payload)
        assert "lines total" in out


# ── B. the two failure modes this change fixes ────────────────────────────

class TestFinishingVocabularyIsSummed:
    def test_finishing_quantity_columns_reach_the_totals_line(self):
        out = summarize(table(FINISHING_COLS, 60))
        t = totals_line(out)
        assert t, "a 60-row table with numeric quantity columns must produce a totals line"
        for col in ("WallPlaster_m2", "WallPaint_m2", "WallTile_m2",
                    "CeilingPlaster_m2", "Skirting_m", "Screed_m3", "FloorArea_m2"):
            assert col in t, f"{col} is a quantity and must be summed"

    def test_unit_suffix_alone_is_enough(self):
        # a quantity column whose name matches no keyword but carries a unit suffix
        out = summarize(table(["Room", "Rebar_kg", "Cable_mm"], 60))
        t = totals_line(out)
        assert "Rebar_kg" in t and "Cable_mm" in t

    def test_blank_first_cell_does_not_erase_the_aggregate(self):
        # ⚠ The assertion must be on the BLANKED column, not on a different one.
        # An earlier version blanked FloorArea_m2 but asserted only that
        # WallPlaster_m2 survived — which stayed true even with the `data[0]`
        # sniff live, so the test could not see the bug it was named for.
        # (Same lesson as D23: assert the CHOICE, not just that a total exists.)
        # 60 rows x 1.5, row 0 blank -> 59 x 1.5 = 88.5, and the column survives.
        out = summarize(table(FINISHING_COLS, 60, first_row={"FloorArea_m2": ""}))
        t = totals_line(out)
        assert t, "one blank cell in row 0 must not delete the whole aggregate"
        assert "FloorArea_m2" in t, "the blanked column itself must still be totalled"
        assert "88.5" in t, "the blank cell contributes 0, it does not remove the column"

    def test_all_blank_first_row_still_totals(self):
        first = {c: "" for c in FINISHING_COLS}
        out = summarize(table(FINISHING_COLS, 60, first_row=first))
        assert has_any_totals(out)


# ── C. a missing aggregate must be SIGNALLED, never silent ────────────────

class TestMissingAggregateIsSignalled:
    def test_no_numeric_column_is_reported_explicitly(self):
        out = summarize(table(["Room", "FloorFinish", "Material"], 60))
        assert not has_any_totals(out)
        assert "no numeric" in out.lower(), \
            "a truncated table with no aggregate must say so, not fail silently"

    def test_signal_names_the_columns_it_considered(self):
        out = summarize(table(["Room", "FloorFinish"], 60))
        low = out.lower()
        assert "room" in low and "floorfinish" in low


# ── D. robustness ────────────────────────────────────────────────────────

class TestNonFiniteSafety:
    def test_nan_and_inf_do_not_poison_the_total(self):
        payload = table(["Room", "Area_m2"], 60)
        payload["structuredOutput"][0]["data"][0]["Area_m2"] = "NaN"
        payload["structuredOutput"][0]["data"][1]["Area_m2"] = "inf"
        t = totals_line(summarize(payload))
        assert "nan" not in t.lower() and "inf" not in t.lower()
        assert "87" in t          # 58 x 1.5, the two bad cells skipped


# ── E. the PRODUCTION wire shape ─────────────────────────────────────────

class TestProductionWireShape:
    """Everything above hands `summarize` a Python list for `data`.

    Production does not. Per protos/corescript.proto:

        message StructuredOutputItem { string type = 1; string data = 2; string title = 3; }

    `data` is a STRING (JSON-encoded), so every real call goes through
    `_parse_data`'s `json.loads` branch. A suite that only ever passes a list
    exercises the pass-through branch and can therefore pass while the shipped
    server is broken. These tests pin the string form and the real entry point.
    """

    @staticmethod
    def _wire(cols, n, title="T"):
        rows = [{**{c: "1.5" for c in cols}, "Room": f"R{i}"} for i in range(n)]
        return [{"type": "table", "title": title, "data": json.dumps(rows)}]

    def test_json_string_data_is_parsed_and_totalled(self):
        out = summarize({"structuredOutput": self._wire(["Room", "Area_m2"], 60)})
        assert "Totals (all 60 rows)" in out
        assert "90" in totals_line(out)          # 60 x 1.5

    def test_json_string_data_truncates_like_the_list_form(self):
        out = summarize({"structuredOutput": self._wire(["Room", "Area_m2"], 60)})
        assert f"showing first {MAX_TABLE_ROWS} + last {TABLE_TAIL_ROWS}" in out

    def test_malformed_json_does_not_raise(self):
        # _parse_data swallows JSONDecodeError and returns the raw string; the
        # item then falls through to the generic branch rather than crashing.
        out = summarize({"structuredOutput": [{"type": "table", "title": "T",
                                               "data": "{not json"}]})
        assert isinstance(out, str) and out

    def test_handle_execution_result_reaches_the_summarizer(self):
        # The entry point the shipped takeoff server actually calls.
        from mcp_core.tools import handle_execution_result
        out = handle_execution_result({
            "is_success": True,
            "output": "",
            "structured_output": self._wire(FINISHING_COLS, 60),
            "internal_data": "",
            "pipeline_diagnostics": [],
        })
        t = totals_line(out)
        assert t, "the real entry point must produce the aggregate"
        for col in ("WallPlaster_m2", "Skirting_m", "Screed_m3"):
            assert col in t
