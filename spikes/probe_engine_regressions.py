#!/usr/bin/env python3
"""Regression asserts for the 2026-10-29 fix round — needs a LIVE Revit session.

The v2.1.0 reviewer asked for exactly this: *"the docs say `WhereParam("Id", …)` was
silently broken until today. It works now, so it's worth a regression test in your
release checks."* Every check below maps to a defect that SHIPPED and was fixed, so a
future change that reintroduces it fails here instead of in a customer's model.

⚠⚠ TWO-SIDED, ALWAYS. Each "must raise" check is paired with a "must still work" check.
   A guard that refuses everything passes a one-sided test — and that is precisely the
   mistake this suite exists to catch: the first draft of the `WhereParam` guard would
   have thrown on the documented `WhereParam("Level", "Level 1")`.

⚠ NON-DESTRUCTIVE — and the restore is an ASSERTION, not a sentence in this docstring.
  The only write is `Comments` on ONE wall, addressed BY ID throughout, captured first
  and restored at the end.

⚠⚠ THIS CLAIM WAS FALSE ONCE (2026-10-29, first live run). The restore used to be a bare
  `execute_dynamic_query` whose result was stored in a variable nobody read, and it used
  `.SetVal(...)` on a COLLECTION — which is the per-element method, so the bulk path it
  actually needed was `.SetParam(...)`. The call returned an error, nothing looked at it,
  and the run continued. The model was left with `Comments="PC-REGRESSION"` on wall
  359588 while this file said "restored at the end … not assumed", and the damage showed
  up as a confusing `missing ['V=[]']` on the NEXT check — which read
  `GetElements("Walls").First()`, i.e. "the same wall" only by luck of ordering.
  Hence three rules here: restore through `check()` so a failed restore FAILS the run,
  address the wall by id so ordering cannot silently retarget it, and never write a
  non-destructive promise that no assertion backs.

Usage:
    <venv-python> spikes/probe_engine_regressions.py
Requires Revit open with a document loaded (ping must report connected).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _harness  # noqa: E402

t = _harness.boot()

results = []          # (label, status, detail)


def check(label, code, want=None, forbid=None):
    """Run `code`; PASS when every `want` appears and no `forbid` does.

    `want`/`forbid` are lists so one call can assert a whole phrase set.
    """
    try:
        out = t.execute_dynamic_query(code, "regression probe")
    except Exception as exc:                                    # noqa: BLE001
        results.append((label, "RAISED", "%s: %s" % (type(exc).__name__, exc)))
        return ""
    flat = out.replace("\n", " ")
    missing = [w for w in (want or []) if w not in out]
    banned = [f for f in (forbid or []) if f in out]
    if missing:
        results.append((label, "FAIL", "missing %r | %s" % (missing, flat[:160])))
    elif banned:
        results.append((label, "FAIL", "contains %r | %s" % (banned, flat[:160])))
    else:
        results.append((label, "PASS", flat[:110]))
    return out


def skip(label, why):
    results.append((label, "SKIP", why))


def check_rows_unique(label, code):
    """Assert a SchemaRows result has no repeated row: `Count() == Distinct().Count()`.

    ⚠ WHY NOT A C# GROUPING (measured 2026-10-29). The obvious assertion —
      `rows.GroupBy(r => r.Name).Where(g => g.Count() > 1)` — CANNOT RUN: the tool
      BLOCKS the `dynamic` token ("Dangerous pattern blocked … no legitimate use"), and
      `Cast<dynamic>()` — which the block message calls the allowed form — fails at
      runtime with "'object' does not contain a definition for 'Scope'". The first
      version of this check therefore reported `missing ['DUP=0']` for a query that had
      been REFUSED, not for duplicates that existed: a test that fails for the wrong
      reason, which is worse than no test. `ToString()` + `Distinct()` needs no dynamic.

    ⚠ WHY COUNTS AND NOT THE PRINTED TABLE. A SchemaRows result is TRUNCATED in the text
      output — measured on a door: "83 lines total (first 24 and last 16)". Parsing that
      window asserts uniqueness over a slice and passes happily while a duplicate hides
      in the middle. Counts are never truncated. (`Peek` is the exception: it is
      capExempt and prints "28 rows, shown in full", so the Peek check parses.)
    """
    try:
        out = t.execute_dynamic_query(code, "regression probe")
    except Exception as exc:                                    # noqa: BLE001
        results.append((label, "RAISED", "%s: %s" % (type(exc).__name__, exc)))
        return ""
    n = next((int(l.split("=", 1)[1].split()[0]) for l in out.splitlines()
              if l.startswith("N=") and "=" in l), None)
    d = next((int(l.split("D=", 1)[1].split()[0]) for l in out.splitlines()
              if l.startswith("N=") and "D=" in l), None)
    if n is None or d is None:
        # An unparseable answer is not a pass — the gate lost its subject.
        results.append((label, "FAIL", "could not read N=/D= from %r" % out[:120]))
        return out
    if n != d:
        results.append((label, "FAIL", "%d row(s), only %d distinct — %d repeat(s)"
                        % (n, d, n - d)))
    else:
        results.append((label, "PASS", "%d rows, %d distinct" % (n, d)))
    return out


def check_peek_unique(label, code, key_cols):
    """Run a `Peek()` dump and FAIL if two rows agree in `key_cols`.

    `Peek` prints its own markdown table ("shown in full" — capExempt), so this parses
    the text. Keyed on Parameter+Storage+StringValue, which is the same triple the
    engine de-dupes on (`Definition.Name` + `StorageType` + the value), so a row this
    calls a duplicate is one the engine should have dropped.
    """
    try:
        out = t.execute_dynamic_query(code, "regression probe")
    except Exception as exc:                                    # noqa: BLE001
        results.append((label, "RAISED", "%s: %s" % (type(exc).__name__, exc)))
        return ""
    header, rows = None, []
    for line in out.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue                                            # |---|---| separator
        if header is None:
            header = cells
            continue
        rows.append(dict(zip(header, cells)))
    if not rows:
        # An empty scan must FAIL — otherwise "no duplicates" is vacuously true.
        results.append((label, "FAIL", "no table rows parsed from the Peek output"))
        return out
    seen, dups = set(), []
    for r in rows:
        key = tuple(r.get(c, "") for c in key_cols)
        if key in seen:
            dups.append("|".join(key))
        seen.add(key)
    if dups:
        results.append((label, "FAIL", "%d row(s), %d duplicate(s): %s"
                        % (len(rows), len(dups), "; ".join(dups[:4]))))
    else:
        results.append((label, "PASS", "%d rows, 0 duplicates in %s"
                        % (len(rows), "/".join(key_cols))))
    return out


print("### 0. connection")
ping = t.ping()
if "connected to Revit" not in ping:
    print(ping[:400])
    sys.exit("NOT CONNECTED — open Revit with a document and re-run.")

# ── the element under test, and its captured Comments ─────────────────────────────
head = check(
    "pick a wall and capture its Comments",
    'var w = GetElements("Walls").First(); '
    'Println("ID=" + w.Id.IntegerValue); '
    'Println("COMMENTS=[" + w.GetStr("Comments") + "]");',
    want=["ID=", "COMMENTS=["],
)
if not head:
    sys.exit("cannot read a wall — nothing to test against")

wall_id = next((l.split("=", 1)[1].strip() for l in head.splitlines() if l.startswith("ID=")), "")
orig_comments = next((l.split("[", 1)[1].rstrip("]") for l in head.splitlines()
                      if l.startswith("COMMENTS=[")), None)
print("    wall=%s  comments=%r" % (wall_id, orig_comments))

# ── 1. THE Id TRAP (operator report [9 -> 0]) ────────────────────────────────────
print("\n### 1. Id resolves as a name — the trap that shipped")

check("GetStr(\"Id\") returns the id, not the element name",
      'Println("V=" + GetElements("Walls").First().GetStr("Id"));',
      want=["V=" + wall_id], forbid=["PC 150"])          # the old wrong answer was the type name

check("GetNum(\"Id\") returns the id as a number",
      'Println("V=" + GetElements("Walls").First().GetNum("Id", ""));',
      want=["V=" + wall_id])

check("WhereParam(\"Id\", int) finds exactly the wall",
      'Println("N=" + GetElements("Walls").WhereParam("Id", %s).Count());' % wall_id,
      want=["N=1"])

check("WhereParam(\"Id\", string) finds exactly the wall",
      'Println("N=" + GetElements("Walls").WhereParam("Id", "%s").Count());' % wall_id,
      want=["N=1"])

check("WhereParam(\"ElementId\", string) finds exactly the wall",
      'Println("N=" + GetElements("Walls").WhereParam("ElementId", "%s").Count());' % wall_id,
      want=["N=1"])

check("an ABSENT id still returns 0 — a real answer, not an error",
      'Println("N=" + GetElements("Walls").WhereParam("Id", "999999999").Count());',
      want=["N=0"])

# ── 2. THE NAME GUARDS — must raise on a typo ────────────────────────────────────
print("\n### 2. a wrong parameter name raises")

check("WhereParam typo raises with a suggestion",
      'GetElements("Walls").WhereParam("Fire Ratng", "2hr").Count();',
      want=["no parameter named", "Did you mean"])

check("GroupByParam typo raises (was: 1 group, silently)",
      'GetElements("Walls").GroupByParam("Nonexistent Param").Count();',
      want=["no parameter named"])

check("SumParam typo raises (was: 0, a plausible total)",
      'GetElements("Walls").SumParam("Nonexistent Param");',
      want=["no parameter named"])

check("OrderByParam typo raises (was: the list, unsorted)",
      'GetElements("Walls").OrderByParam("Nonexistent Param").Count();',
      want=["no parameter named"])

# ── 3. …AND THE SAME GUARDS MUST NOT REFUSE REAL NAMES ──────────────────────────
print("\n### 3. documented names still work (the half a one-sided test misses)")

check("WhereParam(\"Level\") — a magic alias, not a parameter",
      'Println("N=" + GetElements("Walls").WhereParam("Level", "Level 1").Count());',
      want=["N="], forbid=["no parameter named"])

check("WhereParam(\"Type Mark\") — a TYPE-level parameter",
      'Println("N=" + GetElements("Walls").WhereParam("Type Mark", "contains", "").Count());',
      want=["N="], forbid=["no parameter named"])

check("WhereParam(\"Name\") — a native property",
      'Println("N=" + GetElements("Walls").WhereParam("Name", "contains", "").Count());',
      want=["N="], forbid=["no parameter named"])

check("GroupByParam(\"Type Name\", \"Area\", \"m2\") — the summing overload",
      'Println("G=" + GetElements("Walls").GroupByParam("Type Name", "Area", "m2").Count());',
      want=["G="], forbid=["no parameter named"])

check("an EMPTY set with a bogus name does NOT raise — nothing to judge",
      'Println("G=" + GetElements("Walls")'
      '.WhereParam("Comments", "zzz-no-such-value").GroupByParam("Totally Bogus").Count());',
      want=["G=0"], forbid=["no parameter named"])

# ── 4. A REJECTED WRITE IS AN ERROR ─────────────────────────────────────────────
print("\n### 4. a write that cannot happen raises instead of reporting success")

ro = t.execute_dynamic_query(
    'var w = GetElements("Walls").FirstOrDefault(x => x.GetStr("Top Constraint") == "Unconnected"); '
    'Println("RO=" + (w == null ? "none" : w.LookupParameter("Top Offset").IsReadOnly.ToString()) '
    '+ " V=" + (w == null ? "?" : w.GetNum("Top Offset", "mm").ToString()));',
    "find a read-only target",
)
if "RO=True" in ro:
    # ⚠ THE VALUE IS CAPTURED, NOT ASSUMED. This used to assert `V=0` and failed on the big
    # model, where the first unconnected-top wall sits at -300 mm: the write was correctly
    # refused and nothing moved, but the assertion was about THIS MODEL, not about the
    # product. Measure before, compare after — a fixed expected value is a model assumption
    # wearing the clothes of a regression test.
    _before = re.search(r"V=(-?[\d.]+)", ro)
    before_value = _before.group(1) if _before else None
    check("SetNum on a READ-ONLY parameter raises",
          'GetElements("Walls")'
          '.First(x => x.GetStr("Top Constraint") == "Unconnected")'
          '.SetNum("Top Offset", 100, "mm");',
          want=["READ-ONLY"])
    check("…and the value did not change",
          'Println("V=" + GetElements("Walls")'
          '.First(x => x.GetStr("Top Constraint") == "Unconnected").GetNum("Top Offset", "mm"));',
          want=[f"V={before_value}"] if before_value is not None else ["V="])
else:
    skip("SetNum on a READ-ONLY parameter raises",
         "no wall with an unconnected top in this model — cannot construct the case")

# ── 5. no schema view repeats a parameter ───────────────────────────────────────
print("\n### 5. no schema view repeats a parameter")

check_rows_unique(
    "InstanceParams has no repeated row",
    'var rows = GetElements("Doors").First().InstanceParams(); '
    'Println("N=" + rows.Count() + " D=" + rows.Select(r => r.ToString()).Distinct().Count());')

check_rows_unique(
    "CombinedParams has no repeated row",
    'var rows = GetElements("Doors").First().CombinedParams(); '
    'Println("N=" + rows.Count() + " D=" + rows.Select(r => r.ToString()).Distinct().Count());')

# ⚠⚠ THIS IS THE CHECK THE REVIEWER ACTUALLY ASKED FOR. Measured on the build BEFORE
#   the fix (2026-10-29): 28 rows, `Category` twice and `Level` twice — while
#   InstanceParams was already clean at 26. The duplicates live in `Peek`'s own
#   `e.Parameters` loop, not in CombinedParams, which is why fixing InstanceParams
#   alone moved the symptom instead of removing it.
check_peek_unique(
    "Peek() has no repeated row",
    'GetElements("Doors").First().Peek();',
    key_cols=["Parameter", "Storage", "StringValue"])

# ── 6. A real write still works, and is restored ────────────────────────────────
print("\n### 6. a legitimate write still works")

check("SetVal writes and reads back",
      'var w = GetElements("Walls").WhereParam("Id", %s).First(); '
      'w.SetVal("Comments", "PC-REGRESSION"); '
      'Println("V=[" + w.GetStr("Comments") + "]");' % wall_id,
      want=["V=[PC-REGRESSION]"])

check("bulk SetParam still writes the whole collection",
      'Println("N=" + GetElements("Walls").WhereParam("Comments", "PC-REGRESSION").Count());',
      want=["N=1"])

# ⚠⚠ THE RESTORE IS A CHECK, NOT A SIDE EFFECT — see the ⚠⚠ note in the docstring.
#    Addressed BY ID, so a change in element ordering cannot restore a different wall.
#    Written with the PER-ELEMENT `SetVal` on a single element; the collection overload
#    is `SetParam`, and passing `.SetVal` a collection returns an error that nobody read
#    on the first run — leaving the model dirty while this file claimed otherwise.
_orig = (orig_comments or "").replace('"', '\\"')
check("restore the captured Comments (by id)",
      'var w = GetElements("Walls").WhereParam("Id", %s).First(); '
      'w.SetVal("Comments", "%s"); '
      'Println("V=[" + w.GetStr("Comments") + "]");' % (wall_id, _orig),
      want=["V=[%s]" % (orig_comments or "")])

# ⚠ And a collection-wide sweep, because "the one wall I remembered to restore" is a
#   weaker guarantee than "no wall in the model still carries the test value".
check("no wall is left carrying the test value",
      'Println("LEFT=" + GetElements("Walls").WhereParam("Comments", "PC-REGRESSION").Count());',
      want=["LEFT=0"])

# ── verdict ─────────────────────────────────────────────────────────────────────
print()
failed = [r for r in results if r[1] == "FAIL"]
raised = [r for r in results if r[1] == "RAISED"]
skipped = [r for r in results if r[1] == "SKIP"]
passed = [r for r in results if r[1] == "PASS"]

for label, status, detail in results:
    print("%-6s %-58s %s" % (status, label[:58], detail[:90]))

print("\n%d passed, %d failed, %d raised, %d skipped"
      % (len(passed), len(failed), len(raised), len(skipped)))
sys.exit(0 if not failed and not raised else 1)
