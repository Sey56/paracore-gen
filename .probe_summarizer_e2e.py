"""End-to-end probe: what does an AGENT actually receive from the MCP?

Goes through the REAL entry point chain used by the shipped server:
    takeoff_server.py -> handle_execution_result() -> summarize_execution_result() -> summarize()

and uses the REAL wire shape. Per protos/corescript.proto:

    message StructuredOutputItem { string type = 1; string data = 2; string title = 3; }

`data` is a STRING (JSON-encoded), not a list — so the production path always
goes through _parse_data()'s json.loads() branch. A fixture that hands over a
Python list exercises the pass-through branch and therefore does NOT test
production. This probe uses the string.

Run:
    cd paracore-gen
    python .probe_summarizer_e2e.py
"""
import json
import sys

from mcp_core.tools import handle_execution_result

COLS = [
    "Room", "FloorFinish", "FloorArea_m2", "WallPlaster_m2", "WallPaint_m2",
    "WallTile_m2", "CeilingPlaster_m2", "Skirting_m", "Screed_m3",
]


def make_rows(n=60, blank_first_area=False, all_text=False):
    rows = []
    for i in range(n):
        if all_text:
            rows.append({"Room": f"R{i:03d}", "FloorFinish": "TILE", "Material": "Gypsum"})
            continue
        r = {
            "Room": f"R{i:03d}",
            "FloorFinish": "TILE",
            "FloorArea_m2": round(1.5 + i * 0.01, 3),
            "WallPlaster_m2": round(9.0 + i * 0.02, 3),
            "WallPaint_m2": round(9.0 + i * 0.02, 3),
            "WallTile_m2": round(2.0 + i * 0.01, 3),
            "CeilingPlaster_m2": round(1.5 + i * 0.01, 3),
            "Skirting_m": round(12.0 + i * 0.05, 3),
            "Screed_m3": round(0.075 + i * 0.001, 4),
        }
        if blank_first_area and i == 0:
            r["FloorArea_m2"] = ""          # the old code sniffed data[0] only
        rows.append(r)
    return rows


def run(label, rows, title="Room Finishing"):
    # Production shape: data is a JSON *string*, exactly as the proto delivers it.
    result = {
        "is_success": True,
        "output": "",
        "structured_output": [
            {"type": "table", "title": title, "data": json.dumps(rows)}
        ],
        "internal_data": "",
        "pipeline_diagnostics": [],
    }
    text = handle_execution_result(result)
    print("=" * 74)
    print(f"### {label}   ({len(rows)} rows)")
    print("=" * 74)
    print(text)
    print()
    return text


def main():
    fail = 0

    t1 = run("CASE 1 - 60 rooms, all numeric (the normal takeoff)", make_rows(60))
    if "Totals (all 60 rows)" not in t1:
        print("FAIL: no totals line"); fail += 1
    totals = t1.split("Totals (all 60 rows)")[-1] if "Totals (all 60 rows)" in t1 else ""
    for col in ("WallPlaster_m2", "WallPaint_m2", "Skirting_m", "Screed_m3",
                "WallTile_m2", "CeilingPlaster_m2", "FloorArea_m2"):
        if col not in totals:
            print(f"FAIL: {col} missing from totals"); fail += 1
    for col in ("Room", "FloorFinish"):
        if col in totals:
            print(f"FAIL: non-quantity column {col} was summed"); fail += 1

    t2 = run("CASE 2 - same, but row 0 has a BLANK FloorArea_m2 (old: totals VANISHED)",
             make_rows(60, blank_first_area=True))
    if "Totals (all 60 rows)" not in t2:
        print("FAIL: totals line vanished on one blank cell"); fail += 1

    # ⚠ Must exceed SHOW_ALL_TABLE_THRESHOLD (50) or the table is shown in full
    # and correctly needs no aggregate. A 10-row fixture proves nothing.
    t3 = run("CASE 3 - 60 rows, no numeric quantity column (must SAY so, not go silent)",
             make_rows(60, all_text=True))
    if "No numeric quantity column found" not in t3:
        print("FAIL: silent truncation, no signal"); fail += 1

    t4 = run("CASE 4 - small table (12 rows) must pass through untouched", make_rows(12))
    if "Table (12 rows)" not in t4:
        print("FAIL: small table was not passed through verbatim"); fail += 1
    if "Totals" in t4:
        print("FAIL: small table gained a totals line it did not need"); fail += 1

    print("=" * 74)
    print(f"RESULT: {fail} failed")
    print("=" * 74)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
