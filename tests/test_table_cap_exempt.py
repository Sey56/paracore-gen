"""A PARAMETER SCHEMA is never truncated; an ELEMENT DUMP still is.

⚠ Why this exists (2026-10-27): the summariser capped every table at 50 rows + the last 2.
   For an element dump that is right — the agent asked "show me these" and can narrow the
   query. For a parameter schema it is wrong in a way that reads as a model fact: a schema
   cut after 50 rows makes a real parameter look ABSENT, and the agent then stops using it.

   The producer now says which is which (`cap_exempt`, set by the engine for
   .CombinedParams() / .InstanceParams() / .TypeParams() / .BuiltInParams() /
   .NativeProperties() / .Peek()). These pin both halves: the exemption works, AND the cap
   still bites for the tables that should be capped.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, r"C:\Users\seyou\Paracore\paracore\mcp")

from mcp_core.summarizer import summarize, MAX_TABLE_ROWS, TABLE_TAIL_ROWS


def rows(n, cols=("Name", "Storage", "Value")):
    return [{c: f"{c}-{i}" for c in cols} for i in range(1, n + 1)]


def payload(n, cap_exempt=None, cols=("Name", "Storage", "Value")):
    """A single table item. `cap_exempt=None` omits the key entirely (old add-in)."""
    item = {"type": "table", "data": rows(n, cols), "title": ""}
    if cap_exempt is not None:
        item["cap_exempt"] = cap_exempt
    return {"structured_output": [item]}


class TestSchemaTablesAreWhole:
    def test_every_row_of_a_big_schema_survives(self):
        n = 200
        out = summarize(payload(n, cap_exempt=True))
        # Spot-check the head, the middle and the tail — a head+tail cut would lose the middle.
        for i in (1, 100, n):
            assert f"Name-{i}" in out, f"row {i} of {n} is missing"

    def test_it_says_the_table_is_complete(self):
        out = summarize(payload(200, cap_exempt=True))
        assert "shown in full" in out, out[:200]

    def test_it_does_not_offer_a_next_page(self):
        """'N more rows not shown' would send the agent looking for a page that does not exist."""
        out = summarize(payload(200, cap_exempt=True))
        assert "more rows not shown" not in out, out[-300:]

    def test_it_prints_no_totals(self):
        """Summing parameter VALUES is meaningless, and a wrong total is worse than none."""
        out = summarize(payload(200, cap_exempt=True))
        assert "**Totals" not in out, out[-300:]
        assert "Totals (all" not in out, out[-300:]

    def test_a_small_schema_also_says_shown_in_full(self):
        """⚠ A schema is complete REGARDLESS of size (fixed 2026-10-27, review round 6).

        The ``cap_exempt`` branch now sits ABOVE the small-table branch, so a 5-row
        BuiltInParams prints ``Table (5 rows, shown in full)`` just like an 82-row
        CombinedParams. Whether a list is complete is exactly what the agent needs to
        know, and it must not depend on whether the answer happens to be short.
        """
        out = summarize(payload(5, cap_exempt=True))
        assert "shown in full" in out, out[:200]
        assert "Table (5 rows, shown in full)" in out, out[:200]

    def test_json_string_data_is_handled(self):
        """gRPC sends `data` as a JSON string, not a list."""
        item = {"type": "table", "data": json.dumps(rows(200)), "title": "", "cap_exempt": True}
        out = summarize({"structured_output": [item]})
        assert "Name-200" in out, "the JSON-string path lost the tail"


class TestTheCapStillBites:
    def test_an_element_dump_still_caps(self):
        n = 200
        out = summarize(payload(n, cap_exempt=False))
        shown = MAX_TABLE_ROWS + TABLE_TAIL_ROWS
        assert f"Table — {n} rows total" in out, out[:200]
        assert f"showing first {MAX_TABLE_ROWS} + last {TABLE_TAIL_ROWS}" in out, out[:300]
        assert f"{n - shown} more rows not shown" in out, out[-300:]

    def test_the_middle_of_a_capped_table_is_gone(self):
        out = summarize(payload(200, cap_exempt=False))
        assert "Name-100" not in out, "the cap stopped working"

    def test_an_absent_flag_caps(self):
        """⚠ Backward compatibility: an add-in built before the field existed sends nothing.
        Absent must mean False, never True — otherwise an old add-in floods the prompt."""
        out = summarize(payload(200))
        assert "more rows not shown" in out, out[-300:]
        assert "Name-100" not in out

    def test_a_false_flag_caps(self):
        out = summarize(payload(200, cap_exempt=False))
        assert "more rows not shown" in out, out[-300:]


class TestMixedResponse:
    def test_one_schema_and_one_dump_in_the_same_reply(self):
        """The flag is PER ITEM — a snippet that emits both must not promote the dump."""
        items = [
            {"type": "table", "data": rows(200), "title": "schema", "cap_exempt": True},
            {"type": "table", "data": rows(200), "title": "dump", "cap_exempt": False},
        ]
        out = summarize({"structured_output": items})
        assert "shown in full" in out, "the schema item lost its exemption"
        assert "more rows not shown" in out, "the dump item lost its cap"
