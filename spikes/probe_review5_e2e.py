"""End-to-end probe of the review's functional areas, through the REAL tool functions.

Everything the review exercised, re-run against the current source so a change to the
summarizer / schema / skills cannot silently break a working path.

    mcp-build/.venv/Scripts/python.exe spikes/probe_review5_e2e.py

⚠ The probe is SELF-CLEANING: it removes any `E2E_PROBE`-tagged wall before it starts and
after it finishes, so a failed run cannot leave the model changed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ⚠⚠ BOOT THROUGH THE HARNESS, NOT `import mcp_server`. This probe CREATES a wall, and
#   creating one on top of existing geometry raises Revit's "Highlighted walls overlap"
#   warning — a modal dialog that parks Revit's UI thread. A bare `import mcp_server`
#   gives you the tools but NOT the watcher (it starts under `__main__`), and the
#   in-flight gate is skipped too, so nothing can close the dialog and Revit hangs until
#   a human clicks. Measured 2026-10-27 15:42. `boot()` fixes both.
import _harness  # noqa: E402

t = _harness.boot()
server = sys.modules["mcp_server"]

results = []


def check(label, fn, want=None, forbid=None):
    try:
        out = fn()
    except Exception as exc:  # noqa: BLE001
        results.append((label, "RAISED", f"{type(exc).__name__}: {exc}"))
        return ""
    ok, why = True, ""
    if want and want not in out:
        ok, why = False, f"missing {want!r}"
    if forbid and forbid in out:
        ok, why = False, f"contains forbidden {forbid!r}"
    results.append((label, "PASS" if ok else "FAIL", why or out.replace("\n", " ")[:100]))
    return out


def cleanup():
    return t.execute_dynamic_query(
        'GetElements("Walls").WhereParam("Comments", "E2E_PROBE").Delete(); '
        'Println("walls=" + GetElements("Walls").Count());', "e2e cleanup")


print("### 0. start clean")
print("  ", next((l for l in cleanup().splitlines() if l.startswith("walls=")), "?"))

print("### 1. handshake surfaces")
check("ping", t.ping, want="connected")
check("get_context", t.get_context_report, want="Levels")

print("### 2. schema")
check("_search_schema(Walls)", lambda: t.search_schema("Walls"), want="62 parameters")
check("no IntegerValue", lambda: t.search_schema("Walls"), forbid="IntegerValue")
check("bad category", lambda: t.search_schema("Banana Peels"),
      want="No parameters found", forbid="To query")

print("### 3. reads and aggregation")
check("read table (no float noise)", lambda: t.explore_revit_data(
    'GetElements("Walls").Select(e => new { Id = e.Id.Value, H = e.GetNum("Unconnected Height", "m") }).Table()',
    "e2e read"), want="Table (", forbid="0000000004")
check("GroupByParam sum", lambda: t.explore_revit_data(
    'GetElements("Walls").GroupByParam("Type Name", "Area", "m2").Table()', "e2e group"), want="Total")

print("### 4. skills")
# ⚠ EIGHT, not nine (2026-10-27): `create-geometry` was removed — modelling is paracore-model's
#   job, and this server generates REPL on the fly instead of teaching a modelling recipe.
for name in ("query-filter", "aggregate-group", "parameter-access", "write-modify",
             "display-visualize", "discovery-debug",
             "identity-orientation", "materials-units"):
    check(f"read_skill({name})",
          lambda n=name: server.mcp._tool_manager._tools["read_skill"].fn(n),
          forbid="No skill named")

print("### 5. unit-aware write (on an EXISTING wall, restored)")
# ⚠ Before any creation: the probe wall sits on top of existing geometry, and moving its
#   base breaks dimension references — Revit refuses that edit and ROLLS BACK (correctly,
#   and it says so). Testing the unit conversion there would prove the wrong thing.
check("unit write round-trip", lambda: t.execute_dynamic_query(
    'var w = GetElements("Walls").First(); var before = w.GetNum("Base Offset", "mm"); '
    'w.SetNum("Base Offset", 250, "mm"); var after = w.GetNum("Base Offset", "mm"); '
    'w.SetNum("Base Offset", before, "mm"); '
    'Println("mm=" + after + " restored=" + w.GetNum("Base Offset", "mm"));',
    "e2e units"), want="mm=250")

print("### 6. create -> read -> delete")
check("create + tag", lambda: t.execute_dynamic_query(
    'Transact("e2e create", () => { var lvl = GetElements<Level>().First(); '
    'var w = Wall.Create(Doc, Line.CreateBound(new XYZ(0,0,0), new XYZ(3.InputUnit("m"),0,0)), '
    'lvl.Id, false); w.SetVal("Comments", "E2E_PROBE"); }); Println("created");', "e2e create"),
    want="created")
check("read back the tag", lambda: t.explore_revit_data(
    'GetElements("Walls").WhereParam("Comments", "E2E_PROBE")'
    '.Select(e => new { Id = e.Id.Value, Comments = e.GetStr("Comments") }).Table()',
    "e2e verify"), want="E2E_PROBE")
check("delete the probe", cleanup, want="walls=9")

print("### 7. error handling")
check("error: bad param is a warning", lambda: t.explore_revit_data(
    'GetElements("Walls").WhereParam("FireRating", "x").Count().ToString();', "e2e bad param"),
    want="FireRating")
check("error: compile error reports a line", lambda: t.explore_revit_data(
    'var x = ;', "e2e compile error"), want="error CS")

print("\n" + "=" * 78)
for label, status, detail in results:
    print(f"{status:6s} {label:34s} {detail}")
fails = [r for r in results if r[1] != "PASS"]
print(f"\n{len(results) - len(fails)} passed, {len(fails)} failed")
print("final:", next((l for l in cleanup().splitlines() if l.startswith("walls=")), "?"))
sys.exit(1 if fails else 0)
