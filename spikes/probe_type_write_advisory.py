#!/usr/bin/env python3
"""Does the type-write advisory actually FIRE? — the fifth review's blocker.

THE CLAIM (EXTENSION_METHODS.md, "type writes"): `SetVal`/`SetNum` on an instance print a ⚠
when the parameter lives on the TYPE and therefore changes every instance. The reviewer
measured the opposite:

    "Two instance SetVal calls (Fire Rating, Absorptance) silently changed all 4 and all 5
     walls of the type, with no ⚠ on either. I didn't test SetNum on a type parameter.
     This is the one I'd treat as a real bug, because it's a data-safety promise."

WHY IT COULD NOT HAVE FIRED (measured 2026-10-29, before the fix): for a wall,
`w.Parameters` does NOT contain "Fire Rating" and `LookupParameter("Fire Rating")` returns
null — a type parameter reached through an instance can be absent from the instance's own
parameter set. Both `SetNum` and `SetVal` therefore fell into their type-fallback branch,
which called `type.SetVal(...)` and RETURNED, skipping the advisory printed at the bottom of
the method. The guard was not wrong; it was unreachable on the path that actually runs.

⚠⚠ ONE EXECUTION PER CASE — THIS IS THE WHOLE TRICK (learned the hard way, 2026-10-29).
  `_reportedTypeWrites` is keyed on `typeId|parameterName` in the ADD-IN process, which
  outlives every probe run, so a parameter warns exactly ONCE per Revit session. The first
  version of this file called `check()` three times with the same snippet to assert three
  things — so execution 1 printed the ⚠ and consumed it, and executions 2 and 3 saw silence.
  A1 passed, A3 ("names the blast radius") failed, and the failure looked like an engine
  bug. The engine was right. Each case below runs ONCE and every assertion is made against
  that single captured output.
  ⚠ Consequence: RE-RUNNING THIS FILE IN THE SAME REVIT SESSION PROVES NOTHING — the
  parameters are already spent. Restart Revit, or change the parameter names.

⚠⚠ THIS PROBE WRITES TO A TYPE, so it is the most invasive probe in this folder. It is
  judged on what it RESTORES:
    * the original value is read from the TYPE before the write and written back after;
    * each restore is a `check()`, so a failed restore FAILS the run instead of printing;
    * every assertion is two-sided — "the ⚠ appeared" is worthless unless "the write still
      landed on the type" is also true. A guard that REFUSED the write would satisfy the
      first half and break the engine;
    * the numeric case is the one the reviewer did not test, and uses a non-geometric
      parameter (`Absorptance`), so a bad write cannot deform the model.

Usage:
    <venv-python> spikes/probe_type_write_advisory.py            # survey only
    <venv-python> spikes/probe_type_write_advisory.py --write     # survey + advisory test
Requires Revit open with a document loaded, and a FRESH session (see the throttle note).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _harness  # noqa: E402

WRITE = "--write" in sys.argv
t = _harness.boot()

results = []          # (label, status, detail)
MARK = "PC-ADV"


def run(code, label="probe"):
    try:
        return t.execute_dynamic_query(code, label)
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def verdict(label, out, want=None, forbid=None):
    """Judge an ALREADY-CAPTURED output. Use this when the snippet must run only once."""
    missing = [w for w in (want or []) if w not in out]
    banned = [f for f in (forbid or []) if f in out]
    flat = " ".join(out.split())
    if missing:
        results.append((label, "FAIL", "missing %r | %s" % (missing, flat[:200])))
    elif banned:
        results.append((label, "FAIL", "contains %r | %s" % (banned, flat[:200])))
    else:
        results.append((label, "PASS", flat[:130]))


def verdict_numeric(label, out, marker, expected, tol=1e-6):
    """Judge a numeric write by PARSING the value out, never by string formatting.

    ⚠⚠ WHY (measured 2026-10-29, this probe's own bug). The write is asserted with
    `want=["TYPE=[" + ("%.2f" % new)]` — the probe formats the EXPECTATION to 2dp, but the
    engine prints the value with `double.ToString()`, i.e. full precision:

        RAW_CONCAT=[4.999999999999999]   RAW_F2=[5.00]   WOULD_WRITE=[5.049999999999999]

    So writing 5.049999999999999 and reading it back prints `TYPE=[5.049999999999999]`,
    which does not contain `TYPE=[5.05`. The write had LANDED and the check still said
    FAIL — a false red indistinguishable from a data-safety bug. Parse and compare.
    """
    flat = " ".join(out.split())
    m = re.search(re.escape(marker) + r"\[(-?[\d.eE+]+)\]", out)
    if m is None:
        results.append((label, "FAIL", "no %s[<number>] in output | %s" % (marker, flat[:200])))
        return
    got = float(m.group(1))
    if abs(got - expected) > tol:
        results.append((label, "FAIL", "wrote %.9f but type reads %.9f | %s"
                        % (expected, got, flat[:160])))
    else:
        results.append((label, "PASS", "type reads %.9f (wrote %.9f)" % (got, expected)))


def check(label, code, want=None, forbid=None):
    """Run once, then judge. Fine for idempotent reads; NOT for a throttled warning."""
    out = run(code)
    verdict(label, out, want, forbid)
    return out


# ---------------------------------------------------------------------------------
# 1. SURVEY — read only. The baseline is MEASURED, not assumed: if a previous run
#    (mine or the reviewer's) left a marker on a type, it shows up here first.
# ---------------------------------------------------------------------------------
SURVEY = r'''
var walls = GetElements("Walls");
var sb = new System.Text.StringBuilder();
sb.Append("doc=" + Doc.Title + " | walls=" + walls.Count() + "\n");
foreach (var et in GetElements<ElementType>("Walls")) {
    int n = et.TypeInstanceCount();
    if (n == 0) { continue; }
    sb.Append("  [" + et.Name + "] n=" + n + " FR=\"" + et.GetStr("Fire Rating") + "\"");
    var nums = new System.Text.StringBuilder();
    foreach (Parameter p in et.Parameters) {
        if (p.StorageType == StorageType.Double && !p.IsReadOnly) {
            nums.Append(" " + p.Definition.Name + "=" + et.GetNum(p.Definition.Name));
        }
    }
    sb.Append("  double:" + nums.ToString() + "\n");
}
return sb.ToString();
'''

print("=" * 78)
print("SURVEY (read-only)")
print("=" * 78)
survey = run(SURVEY, "survey")
print(survey)

# Parse the survey rather than hard-coding type names: this model's types are "PC 150 …"
# and "PC 115 …", but a probe that only works on one operator's test file is not a probe.
types = []
for line in survey.splitlines():
    m = re.match(r'\s*\[(?P<name>[^\]]+)\]\s+n=(?P<n>\d+)\s+FR="(?P<fr>[^"]*)"\s+double:(?P<nums>.*)$',
                 line)
    if not m:
        continue
    nums = dict(re.findall(r'(\S+)=(-?[\d.]+)', m.group("nums")))
    types.append({"name": m.group("name"), "n": int(m.group("n")),
                  "fr": m.group("fr"), "nums": nums})

if not WRITE:
    print()
    print("Survey only. Re-run with --write to exercise the advisory "
          "(⚠ writes a type parameter, then restores it).")
    sys.exit(0)

if not types:
    print("No wall type with instances — cannot test a blast radius. Stopping.")
    sys.exit(1)

A = types[0]
B = types[1] if len(types) > 1 else types[0]

# ⚠ `--swap` exists because the throttle is spent per (type, parameter) for the life of the
#   Revit process. Running this file twice in one session must use DIFFERENT pairs or the
#   warning cannot appear — which would look exactly like the bug coming back. Swapping the
#   two types gives each case a parameter it has not used yet (FR on the second type,
#   Absorptance on the first). A fresh Revit needs no flag.
if "--swap" in sys.argv and len(types) > 1:
    A, B = B, A
print()
print("CASE A -> type %r, n=%d, FR=%r" % (A["name"], A["n"], A["fr"]))
print("CASE B -> type %r, n=%d, numeric=%r" % (B["name"], B["n"], B["nums"]))

# A numeric TYPE parameter for case B. `Absorptance` is preferred because it is
# non-geometric; a width-like parameter could deform the model if the RESTORE is what fails.
num_name = "Absorptance" if "Absorptance" in B["nums"] else (list(B["nums"])[0] if B["nums"] else None)

# ---------------------------------------------------------------------------------
# 2. CASE A — SetVal on a STRING type parameter (the reviewer's own case).
#    ONE execution; three assertions against its output.
# ---------------------------------------------------------------------------------
WRITE_A = r'''
var et = GetElements<ElementType>("Walls").FirstOrDefault(x => x.Name == "%s");
if (et == null) { return "NO TYPE"; }
var w = GetElements("Walls").FirstOrDefault(x => x.GetTypeId() == et.Id);
if (w == null) { return "NO INSTANCE"; }
w.SetVal("Fire Rating", "%s-A");
return "TYPE=[" + et.GetStr("Fire Rating") + "] n=" + et.TypeInstanceCount();
''' % (A["name"], MARK)

out_a = run(WRITE_A, "case A")
verdict("A1. SetVal on a TYPE param PRINTS the advisory", out_a,
        want=["is a TYPE parameter on", "instance(s) of it change together"],
        forbid=["Execution Failed"])
verdict("A2. ...and the write still LANDS on the type", out_a,
        want=["TYPE=[" + MARK + "-A]"])
verdict("A3. ...naming the real blast radius (%d)" % A["n"], out_a,
        want=["all %d instance(s)" % A["n"]])

RESTORE_A = r'''
var et = GetElements<ElementType>("Walls").FirstOrDefault(x => x.Name == "%s");
if (et == null) { return "NO TYPE"; }
et.SetVal("Fire Rating", "%s");
return "RESTORED FR=[" + et.GetStr("Fire Rating") + "]";
''' % (A["name"], A["fr"])

check("A4. RESTORED Fire Rating to %r" % A["fr"],
      RESTORE_A, want=["RESTORED FR=[" + A["fr"] + "]"])

# ---------------------------------------------------------------------------------
# 3. CASE B — SetNum on a NUMERIC type parameter (the case the reviewer did not test).
#    ONE execution; three assertions against its output.
# ---------------------------------------------------------------------------------
if num_name is None:
    results.append(("B1. SetNum on a TYPE param", "SKIP", "no writable double param on the type"))
else:
    orig = B["nums"][num_name]
    new = float(orig) + 0.05
    WRITE_B = r'''
var et = GetElements<ElementType>("Walls").FirstOrDefault(x => x.Name == "%s");
if (et == null) { return "NO TYPE"; }
var w = GetElements("Walls").FirstOrDefault(x => x.GetTypeId() == et.Id);
if (w == null) { return "NO INSTANCE"; }
w.SetNum("%s", %s, "");
return "TYPE=[" + et.GetNum("%s") + "] n=" + et.TypeInstanceCount();
''' % (B["name"], num_name, new, num_name)

    out_b = run(WRITE_B, "case B")
    verdict("B1. SetNum on a TYPE param PRINTS the advisory", out_b,
            want=["is a TYPE parameter on", "instance(s) of it change together"],
            forbid=["Execution Failed"])
    verdict_numeric("B2. ...and the numeric write LANDS on the type", out_b, "TYPE=", new)
    verdict("B3. ...naming the real blast radius (%d)" % B["n"], out_b,
            want=["all %d instance(s)" % B["n"]])

    RESTORE_B = r'''
var et = GetElements<ElementType>("Walls").FirstOrDefault(x => x.Name == "%s");
if (et == null) { return "NO TYPE"; }
et.SetNum("%s", %s, "");
return "RESTORED %s=[" + et.GetNum("%s") + "]";
''' % (B["name"], num_name, orig, num_name, num_name)

    check("B4. RESTORED %s to %s" % (num_name, orig),
          RESTORE_B, want=["RESTORED " + num_name + "=[" + orig])

# ---------------------------------------------------------------------------------
# 4. FINAL SWEEP — the model must be exactly as found. Re-run the survey and compare
#    the fields this probe could have touched.
# ---------------------------------------------------------------------------------
after = run(SURVEY, "survey after")
drift = []
for before_row in types:
    m = re.search(r'\[%s\] n=\d+ FR="([^"]*)"' % re.escape(before_row["name"]), after)
    if not m:
        drift.append(before_row["name"] + " MISSING")
        continue
    if m.group(1) != before_row["fr"]:
        drift.append("%s FR %r -> %r" % (before_row["name"], before_row["fr"], m.group(1)))
    if num_name and num_name in before_row["nums"]:
        # ⚠⚠ Per-row anchoring (fixed 2026-10-29). The previous version searched the WHOLE
        #   `after` survey text for `num_name=...`, so every type was compared against the
        #   FIRST type that had that parameter. A correct restore therefore reported as
        #   drift on every other type — e.g. BedDoorWin's Spacing read as Storefront's.
        #   Anchor on the row: take the line for THIS type, then look for num_name inside it.
        row_m = re.search(r'^\s*\[%s\]\s+n=\d+\s+FR="[^"]*"\s+double:(.*)$'
                          % re.escape(before_row["name"]), after, re.MULTILINE)
        if row_m:
            mn = re.search(r'%s=(-?[\d.]+)' % re.escape(num_name), row_m.group(1))
            if mn and mn.group(1) != before_row["nums"][num_name]:
                drift.append("%s %s %s -> %s" % (before_row["name"], num_name,
                                                 before_row["nums"][num_name], mn.group(1)))

if drift:
    results.append(("C1. model left EXACTLY as found", "FAIL", "; ".join(drift)))
else:
    results.append(("C1. model left EXACTLY as found", "PASS", "no drift on FR / " + str(num_name)))

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
