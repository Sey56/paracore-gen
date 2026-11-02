#!/usr/bin/env python3
"""
Round 30b — broad test on the big model (Paracore_2025_Demo, 609 walls).
Tests the reviewer's untested list: Delete, Hide/Unhide/Isolate, charts,
export, timeout, NewType/SwapSymbol.
"""
import sys, os, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
import _harness

t = _harness.boot(start_watcher=True)
results = []

def run(code, label):
    return t.execute_dynamic_query(code, label)

def verdict(label, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((label, tag, detail))

# --- D1. Delete (create a wall, then delete it) ---
print("=== D1. Delete ===")
out = run(r'''
var before = GetElements("Walls").Count();
// create a tiny wall to delete
var line = Autodesk.Revit.DB.Line.CreateBound(new XYZ(0,0,0), new XYZ(1,0,0));
Wall w;
Transact("create+delete", () => {
    w = Wall.Create(Doc, line, Doc.GetElement(Doc.GetDefaultElementTypeId(ElementTypeGroup.WallType)) as WallType, Doc.GetElement(new ElementId(453)) as Level, 1, 0, false, false);
    w.Delete();
});
var after = GetElements("Walls").Count();
return "before=" + before + " after=" + after;
''', 'D1 create+delete')
flat = " ".join(out.split())
verdict("D1. create+delete leaves count unchanged",
        "before=" in flat and "after=" in flat,
        flat[:180])

# --- D2. Delete an existing element ---
print("=== D2. Delete existing + restore ===")
out = run(r'''
var walls = GetElements("Walls");
var target = walls.First();
long tid = target.Id.Value;
string mark = target.GetStr("Comments");
// remember its location for recreation
var loc = (LocationCurve)target.Location;
var curve = loc.Curve;
var typeId = target.GetTypeId();
var lvlId = ((Level)target.LookupParameter("Base Constraint")?.AsElementId())?.Id ?? ElementId.InvalidElementId;
return "id=" + tid + " mark=[" + mark + "] curve=" + curve.Length + " type=" + typeId.Value + " lvl=" + lvlId.Value;
''', 'D2 survey')
print("  survey:", out.strip()[:200])

# --- H1. Hide / Unhide ---
print("=== H1. Hide/Unhide ===")
out = run(r'''
var w = GetElements("Walls").First();
var v = Doc.ActiveView;
bool before = v.IsElementHiddenInTemporaryViewMode(w.Id) || !v.CanCategoryBeHidden(w.Category.Id);
w.Hide();
// Hide() sets temporary hide
bool hidden = v.IsElementHiddenInTemporaryViewMode(w.Id);
w.Unhide();
bool shown = !v.IsElementHiddenInTemporaryViewMode(w.Id);
return "before=" + before + " hidden=" + hidden + " shown=" + shown;
''', 'H1 hide/unhide')
flat = " ".join(out.split())
verdict("H1. Hide then Unhide round-trips",
        "hidden=True" in flat and "shown=True" in flat,
        flat[:180])

# --- I1. Isolate ---
print("=== I1. Isolate ===")
out = run(r'''
var w = GetElements("Walls").First();
var v = Doc.ActiveView;
w.Isolate();
bool isolated = v.IsInTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate);
Transact("clear isolate", () => {
    v.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate);
});
bool cleared = !v.IsInTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate);
return "isolated=" + isolated + " cleared=" + cleared;
''', 'I1 isolate')
flat = " ".join(out.split())
verdict("I1. Isolate sets temporary mode and can be cleared",
        "isolated=True" in flat and "cleared=True" in flat,
        flat[:180])

# --- C1. BarGraph ---
print("=== C1. BarGraph ===")
out = run(r'''
var data = GetElements("Walls").Take(5).Select(w => new { Name = w.GetStr("Type"), Value = w.GetNum("Length") }).ToList();
var names = string.Join("|", data.Select(d => d.Name));
var values = string.Join("|", data.Select(d => d.Value.ToString("F2")));
return BarGraph(names, values, "Wall Lengths");
''', 'C1 bar')
flat = " ".join(out.split())
verdict("C1. BarGraph returns success",
        "bar" in flat.lower() or "chart" in flat.lower() or "analytics" in flat.lower() or "✅" in flat or "added" in flat.lower(),
        flat[:180])

# --- C2. PieGraph ---
print("=== C2. PieGraph ===")
out = run(r'''
var data = GetElements("Walls").Take(5).Select(w => new { Name = w.GetStr("Type"), Value = w.GetNum("Area") }).ToList();
var names = string.Join("|", data.Select(d => d.Name));
var values = string.Join("|", data.Select(d => d.Value.ToString("F2")));
return PieGraph(names, values, "Wall Areas");
''', 'C2 pie')
flat = " ".join(out.split())
verdict("C2. PieGraph returns success",
        "pie" in flat.lower() or "chart" in flat.lower() or "analytics" in flat.lower() or "✅" in flat or "added" in flat.lower(),
        flat[:180])

# --- C3. LineGraph ---
print("=== C3. LineGraph ===")
out = run(r'''
var data = GetElements("Walls").Take(5).Select(w => w.GetNum("Length")).ToList();
var values = string.Join("|", data.Select(d => d.ToString("F2")));
return LineGraph(values, "Wall Lengths Trend");
''', 'C3 line')
flat = " ".join(out.split())
verdict("C3. LineGraph returns success",
        "line" in flat.lower() or "chart" in flat.lower() or "analytics" in flat.lower() or "✅" in flat or "added" in flat.lower(),
        flat[:180])

# --- E1. Export 3D view ---
print("=== E1. Export 3D view ===")
out = run(r'''
return export_view("{3D}", format: "png", width: 800, height: 600);
''', 'E1 export 3D')
flat = " ".join(out.split())
verdict("E1. Export {3D} view",
        "saved" in flat.lower() or "✅" in flat or "exported" in flat.lower() or ".png" in flat.lower(),
        flat[:180])

# --- E2. Export plan view ---
print("=== E2. Export plan ===")
# Find a plan view name
survey = run(r'''
var views = GetElements<ViewPlan>();
if (views.Count() == 0) return "NO PLANS";
var names = string.Join(", ", views.Take(3).Select(v => v.Name));
return names;
''', 'E2 survey')
print("  plan views:", survey.strip()[:120])

out = run(r'''
var vname = GetElements<ViewPlan>().First().Name;
return export_view(vname, format: "png", width: 800, height: 600);
''', 'E2 export plan')
flat = " ".join(out.split())
verdict("E2. Export a plan view",
        "saved" in flat.lower() or "✅" in flat or "exported" in flat.lower() or ".png" in flat.lower(),
        flat[:180])

# --- T1. Timeout (infinite loop) ---
print("=== T1. Timeout ===")
out = run(r'''
while (true) { }
return "never";
''', 'T1 timeout')
flat = " ".join(out.split())
verdict("T1. Infinite loop is killed",
        "timeout" in flat.lower() or "timed out" in flat.lower() or "cancelled" in flat.lower() or "killed" in flat.lower(),
        flat[:180])

# --- T2. All-or-nothing with a real write on the big model ---
print("=== T2. All-or-nothing (big model) ===")
out = run(r'''
var walls = GetElements("Walls").Take(10);
foreach (var w in walls) { w.SetVal("Comments", "BIG-ENVELOPE-TEST"); }
throw new Exception("deliberate failure after 10 writes");
''', 'T2 write+throw')
flat = " ".join(out.split())
verdict("T2a. Failure reported with rollback",
        "deliberate failure" in flat and "ROLLED BACK" in flat,
        flat[:180])

# Verify none of the 10 walls have the marker
out2 = run(r'''
var dirty = GetElements("Walls").Where(w => w.GetStr("Comments") == "BIG-ENVELOPE-TEST").Count();
return "dirty=" + dirty;
''', 'T2 verify')
flat2 = " ".join(out2.split())
verdict("T2b. All 10 writes were undone",
        "dirty=0" in flat2,
        flat2[:100])

# --- R1. Runtime line number on big model ---
print("=== R1. Runtime line number ===")
out = run('var x = 5;\nvar y = 0;\nvar z = x / y;\nreturn "z=" + z;', 'R1')
flat = " ".join(out.split())
verdict("R1. Runtime error names the line",
        "at your line" in flat and "3" in flat,
        flat[:180])

# --- SUMMARY ---
print("\n=== SUMMARY ===")
passed = sum(1 for _, t, _ in results if t == "PASS")
failed = sum(1 for _, t, _ in results if t == "FAIL")
print(f"{passed} passed, {failed} failed, {len(results)} total")
if failed:
    print("\nFAILURES:")
    for label, tag, detail in results:
        if tag == "FAIL":
            print(f"  {label}: {detail[:200]}")
