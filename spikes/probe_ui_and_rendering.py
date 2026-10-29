#!/usr/bin/env python3
"""The reviewer's untested UI surface — Hide / Unhide / Isolate, Table, charts, flipHand.

None of these were exercised before the v2.1.0 review. All are REVERSIBLE, and this file
puts each one back:

    Hide/Unhide      asserted with `Element.IsHidden(view)`, not by eye
    Isolate          `Isolate()` uses `IsolateElementTemporary`, i.e. Revit's temporary
                     hide/isolate mode. There is NO `Unisolate()` in the engine, so the
                     probe clears the mode through the raw API — otherwise it would leave
                     the operator's view isolated with no documented way back. That gap is
                     a finding in its own right, reported below.
    flipHand         there is no Paracore `flipHand`; `door.flipHand()` is the Revit API
                     method. Tested as a ROUND TRIP: flip, read, flip back, read.
    Table/charts     rendered output only; asserted to produce no Execution Failed.

⚠ TWO-SIDED. `IsHidden` is checked BEFORE and AFTER each call: "Hide() did not error" is
  not the same as "the element is hidden", and an element already hidden would make an
  Unhide-only test pass while doing nothing.

Usage:
    <venv-python> spikes/probe_ui_and_rendering.py
Requires Revit open with a document loaded.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _harness  # noqa: E402

t = _harness.boot()

results = []


def run(code, label="ui-probe"):
    try:
        return t.execute_dynamic_query(code, label)
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def _evidence(out):
    flat = " ".join(out.split())
    for marker in ("no matches.'", "see the `read_skill` skills.", "BEFORE proceeding."):
        if marker in flat:
            flat = flat.split(marker, 1)[1].strip()
    return flat


def verdict(label, out, want=None, forbid=None):
    missing = [w for w in (want or []) if w not in out]
    banned = [f for f in (forbid or []) if f in out]
    flat = _evidence(out)
    if missing:
        results.append((label, "FAIL", "missing %r | %s" % (missing, flat[:190])))
    elif banned:
        results.append((label, "FAIL", "contains %r | %s" % (banned, flat[:190])))
    else:
        results.append((label, "PASS", flat[:150]))


def check(label, code, want=None, forbid=None):
    out = run(code)
    verdict(label, out, want, forbid)
    return out


# ---------------------------------------------------------------------------------
# 1. Hide / Unhide — one wall, by id, state read before and after.
# ---------------------------------------------------------------------------------
HIDE = r'''
var w = GetElements("Walls").First();
var v = Doc.ActiveView;
string before = w.IsHidden(v).ToString();
w.Hide();
string hidden = w.IsHidden(v).ToString();
w.Unhide();
string after = w.IsHidden(v).ToString();
return "id=" + w.Id.Value + " before=" + before + " afterHide=" + hidden + " afterUnhide=" + after;
'''

out = check("U1. Hide() actually hides, and Unhide() restores", HIDE,
            want=["before=False", "afterHide=True", "afterUnhide=False"],
            forbid=["Execution Failed"])

# If a model ever starts with the wall already hidden the pattern above cannot match; say so
# rather than reporting a mysterious failure.
if "before=True" in out:
    results.append(("U1b. wall started VISIBLE (needed for a clean two-sided test)",
                    "SKIP", "first wall was already hidden — re-run on a visible wall"))

# ---------------------------------------------------------------------------------
# 2. Isolate — temporary view mode, asserted, then cleared.
# ---------------------------------------------------------------------------------
ISOLATE = r'''
var w = GetElements("Walls").First();
var v = Doc.ActiveView;
bool canTemp = v.CanEnableTemporaryViewPropertiesMode();
w.Isolate();
bool on = v.IsInTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate);
// ⚠ `DisableTemporaryViewMode` is RAW Revit API — it is NOT auto-transacted. The engine's
//   auto-transaction covers Paracore methods (`Isolate`, `Hide`, `SetVal`); a bare API call
//   that modifies the document raises "Attempt to modify the model outside of transaction."
//   That is what this probe hit on its first run, and it is a doc gap: the globals sheet
//   says the tool is "auto-transacted" without qualifying that raw API writes are not.
Transact("reset isolate", () => v.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate));
bool off = v.IsInTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate);
return "canTemp=" + canTemp + " modeAfterIsolate=" + on + " modeAfterReset=" + off;
'''

check("U2. Isolate() enters the TEMPORARY hide/isolate mode", ISOLATE,
      want=["modeAfterIsolate=True"], forbid=["Execution Failed"])
check("U3. ...and the mode can be cleared again (no stranded view)", ISOLATE,
      want=["modeAfterReset=False"])

# ⚠ U2/U3 re-run the snippet, which is harmless here (Isolate is idempotent and the second
#   call re-clears). Unlike the type-write advisory there is no per-session throttle.

# ---------------------------------------------------------------------------------
# 3. Table and charts — rendered output, asserted only to not fail.
# ---------------------------------------------------------------------------------
check("U4. unprojected .Table() renders", r'''
GetElements("Walls").Table();
return "table ok";
''', want=["table ok"], forbid=["Execution Failed", "error CS"])

check("U5. .Select(...).Table() renders", r'''
GetElements("Walls").Select(e => new { Id = e.Id.Value, Type = e.GetStr("Type") }).Table();
return "select table ok";
''', want=["select table ok"], forbid=["Execution Failed", "error CS"])

for kind in ("BarGraph", "PieGraph", "LineGraph"):
    check("U6. %s() renders a grouped result" % kind, r'''
GetElements("Walls").GroupByParam("Type", "Length", "m").%s();
return "%s ok";
''' % (kind, kind), want=["%s ok" % kind], forbid=["Execution Failed", "error CS"])

# ---------------------------------------------------------------------------------
# 4. flipHand — round trip on a real door.
# ---------------------------------------------------------------------------------
FLIP = r'''
var fi = GetElements<FamilyInstance>("Doors").FirstOrDefault();
if (fi == null) { return "NO DOORS"; }
bool start = fi.IsHandFlipped();
// ⚠ flipHand() is RAW Revit API — see the note in ISOLATE: not auto-transacted.
Transact("flip hand", () => fi.flipHand());
bool mid = fi.IsHandFlipped();
Transact("flip hand back", () => fi.flipHand());
bool end = fi.IsHandFlipped();
return "id=" + fi.Id.Value + " start=" + start + " flipped=" + mid + " back=" + end;
'''

out = check("U7. door.flipHand() flips, and flipping twice restores", FLIP,
            want=["flipped="], forbid=["Execution Failed"])

if "NO DOORS" in out:
    results.append(("U7b. door round trip", "SKIP", "no doors in this model"))
else:
    # ⚠⚠ Parse the actual transitions, never `in` substring checks (fixed 2026-10-29).
    #   The previous U8 branch treated `start=True flipped=False` as FAILURE ("flipHand did
    #   nothing"). That is exactly what a WORKING flip looks like: the state genuinely
    #   transitioned True→False on the flip and False→True on the restore. The branch was
    #   inverted, and the bug was indistinguishable from a real flip no-op.
    #   Measured: PHASE0 hand=True → PHASE1 hand=False → PHASE2 hand=True.
    import re as _re
    m = _re.search(r'start=(True|False)\s+flipped=(True|False)\s+back=(True|False)', out)
    if m is None:
        results.append(("U8. flip is a real toggle and the restore holds", "FAIL",
                        "could not parse start/flipped/back from: " + _evidence(out)[:160]))
    else:
        s, f, b = (g == "True" for g in m.groups())
        toggled = (s != f)            # flip changed the state
        restored = (s == b)           # second flip returned to the original
        ok = toggled and restored
        results.append(("U8. flip is a real toggle and the restore holds",
                        "PASS" if ok else "FAIL",
                        "start=%s flipped=%s back=%s (%s toggle, %s restore)"
                        % (s, f, b,
                           "real" if toggled else "NO",
                           "holds" if restored else "BROKEN")))

print()
print("=" * 78)
print("RESULTS")
print("=" * 78)
width = max(len(r[0]) for r in results)
fails = 0
for label, status, detail in results:
    if status not in ("PASS", "SKIP"):
        fails += 1
    print("%-*s  %-6s  %s" % (width, label, status, detail))
print()
print("%d passed, %d failed" % (len(results) - fails, fails))
sys.exit(1 if fails else 0)
