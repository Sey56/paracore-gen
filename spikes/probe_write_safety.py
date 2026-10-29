#!/usr/bin/env python3
"""The WRITE-SAFETY promises — rejected writes, and bulk atomicity.

The reviewer's untested list named the "rollback layer of read-only enforcement".
EXTENSION_METHODS.md makes three claims, each of which is a data-safety promise:

  P1  `SetNum`/`SetVal` RAISE for an unknown parameter name — they do not write nothing
      and let the transaction report success.
  P2  `SetNum`/`SetVal` RAISE for a read-only parameter, and nothing is written.
  P3  `.SetParam()` over a collection runs in ONE transaction, so the first element that
      refuses aborts the whole write and NOTHING is applied.

P3 is the interesting one: "nothing is applied" is only observable when the failure happens
AFTER some elements have already accepted the value. A test that fails on the FIRST element
proves nothing about rollback — it would pass against an implementation with no transaction
at all. So the atomicity case writes to every wall and THEN throws, and asserts that the
first walls are clean afterwards.

⚠ EVERY test here is two-sided. "The write was refused" is worthless unless "a legal write
  still lands" is also true — otherwise a settable that refuses everything passes.
⚠ THIS FILE WRITES `Comments` ON EVERY WALL and restores them from a snapshot taken before
  the first write. The snapshot lives in a REPL SESSION VARIABLE (`__safeSnap`), not in the
  reply — the reply truncates multi-line output to 40 lines, and a snapshot parsed from it
  silently captured 40 of 609 walls. The restore is asserted by count AND by a drift count
  computed in C#, so a truncated read cannot make either check pass falsely.

Usage:
    <venv-python> spikes/probe_write_safety.py
Requires Revit open with a document loaded.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _harness  # noqa: E402

t = _harness.boot()

results = []
MARK = "PC-SAFE"


def run(code, label="write-safety"):
    try:
        return t.execute_dynamic_query(code, label)
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def _evidence(out):
    """Drop the advisory preamble so the DETAIL shows what the check actually looked at.

    ⚠ Every earlier probe in this folder printed `flat[:130]`, which is the WORKFLOW
    WARNING banner — so a PASS and a FAIL looked identical and the evidence beside the
    verdict was never the evidence. The banner is not part of the answer.
    """
    flat = " ".join(out.split())
    for marker in ("no matches.'", "see the `read_skill` skills."):
        if marker in flat:
            flat = flat.split(marker, 1)[1].strip()
    return flat


def verdict(label, out, want=None, forbid=None):
    missing = [w for w in (want or []) if w not in out]
    banned = [f for f in (forbid or []) if f in out]
    flat = _evidence(out)
    if missing:
        results.append((label, "FAIL", "missing %r | %s" % (missing, flat[:200])))
    elif banned:
        results.append((label, "FAIL", "contains %r | %s" % (banned, flat[:200])))
    else:
        results.append((label, "PASS", flat[:150]))


def check(label, code, want=None, forbid=None):
    out = run(code)
    verdict(label, out, want, forbid)
    return out


# ---------------------------------------------------------------------------------
# 0. SNAPSHOT — every wall's id and Comments, before anything is written.
#
# ⚠⚠ THE SNAPSHOT LIVES IN THE REPL SESSION, NOT IN THE REPLY (fixed 2026-10-29).
#   The MCP reply TRUNCATES multi-line output to 40 lines. Measured on the 609-wall
#   demo model: the previous version returned one `id=value` line per wall, the reply
#   carried 851 chars / 40 lines, and the probe parsed exactly 40 walls while believing
#   it had all 609. The restore then put back only those 40 — and because
#   `GetElements("Walls")` ordering is not stable between submissions, the 40 walls it
#   WROTE were not the 40 it had SNAPSHOTTED. Result: 16 walls left carrying
#   `PC-SAFE-*` on every run, while R1 reported "every wall RESTORED" — because R1
#   compared against the same truncated snapshot.
#   ⚠ A truncated read is not a measurement, and an assertion that compares a truncated
#     baseline to itself cannot fail. The values now stay in a session variable; only a
#     COUNT crosses the reply boundary.
# ---------------------------------------------------------------------------------
SNAP = r'''
var __safeSnap = new System.Collections.Generic.Dictionary<long, string>();
foreach (var w in GetElements("Walls")) {
    __safeSnap[w.Id.Value] = w.GetStr("Comments");
}
Println("SNAP_COUNT=" + __safeSnap.Count);
Println("WALL_COUNT=" + GetElements("Walls").Count());
'''

snap_raw = run(SNAP, "snapshot")
print("=" * 78)
print(snap_raw.strip()[:400])
print("=" * 78)

import re as _re
_m_snap = _re.search(r"SNAP_COUNT=(\d+)", snap_raw)
_m_wall = _re.search(r"WALL_COUNT=(\d+)", snap_raw)
snap_count = int(_m_snap.group(1)) if _m_snap else None
wall_count = int(_m_wall.group(1)) if _m_wall else None

if snap_count is None or wall_count is None:
    print("Could not read SNAP_COUNT/WALL_COUNT — refusing to run a probe whose")
    print("baseline is unproven. Stopping.")
    sys.exit(1)

# ⚠ The snapshot must cover EVERY wall, or the restore cannot cover every write.
#   This is the assertion the old version lacked.
if snap_count != wall_count:
    print("SNAPSHOT INCOMPLETE: %d of %d walls captured — refusing to write."
          % (snap_count, wall_count))
    sys.exit(1)

print("SNAPSHOT — %d wall(s), held in the REPL session as __safeSnap" % snap_count)
if not snap_count:
    print("No walls — cannot run. Stopping.")
    sys.exit(1)

# A read-only parameter to aim P2 at. `Area` is computed by Revit and is read-only on a
# wall; if a model ever makes it writable the probe says so instead of silently passing.
READONLY_NAME = "Area"

# ---------------------------------------------------------------------------------
# 1. P1 — an unknown parameter name must RAISE, not silently do nothing
# ---------------------------------------------------------------------------------
out = run(r'''
var w = GetElements("Walls").First();
w.SetVal("Fire Ratng", "2 hr");
return "NO EXCEPTION — the write was accepted";
''', "P1 unknown name")

verdict("P1a. unknown name RAISES", out,
        want=["no parameter of that name"],
        forbid=["NO EXCEPTION"])
verdict("P1b. ...and suggests the real name", out, want=["Did you mean"])

# Two-sided: the correctly spelled name still works (it is a TYPE param — this also
# re-proves the advisory path, and the restore below puts it back).
out = run(r'''
var w = GetElements("Walls").First();
w.SetVal("Comments", "%s-P1");
return "comments=[" + w.GetStr("Comments") + "]";
''' % MARK, "P1 control")

verdict("P1c. control — a legal write still LANDS", out, want=["comments=[" + MARK + "-P1]"])

# ---------------------------------------------------------------------------------
# 2. P2 — a read-only parameter must RAISE, and nothing is written
# ---------------------------------------------------------------------------------
out = run(r'''
var w = GetElements("Walls").First();
var p = w.LookupParameter("%s");
if (p == null) { return "ABSENT — cannot test read-only on this model"; }
if (!p.IsReadOnly) { return "WRITABLE — %s is not read-only here, so P2 cannot be tested"; }
w.SetNum("%s", 1.0, "");
return "NO EXCEPTION — the read-only write was accepted";
''' % (READONLY_NAME, READONLY_NAME, READONLY_NAME), "P2 read-only")

if "ABSENT" in out or "WRITABLE" in out:
    results.append(("P2. read-only write RAISES", "SKIP", " ".join(out.split())[:150]))
else:
    verdict("P2. read-only write RAISES", out,
            want=["READ-ONLY"],
            forbid=["NO EXCEPTION"])

# ---------------------------------------------------------------------------------
# 3. P3 — bulk atomicity: write to EVERY wall, then fail. Nothing may survive.
#    ⚠ The throw is AFTER the write on purpose. Failing on the first element would
#      pass even with no transaction at all.
# ---------------------------------------------------------------------------------
# ⚠ SCOPE IS BOUNDED ON PURPOSE (fixed 2026-10-29). This used to write `Comments` on
# `GetElements("Walls")` — every wall in whatever model is open. On the 609-wall demo model
# that is 609 writes for a test whose point is "the first few were undone", and the restore
# below only knew about the snapshot ids it had printed. It left 569 walls carrying
# `PC-SAFE-OK` while reporting P3/P4 results. A probe must not be able to touch more of the
# model than it can put back: 40 walls is enough to prove atomicity and cheap to restore.
SCOPE = 40
out = run(r'''
var walls = GetElements("Walls").Take(40).ToList();
bool caught = false;
try {
    Transact("atomicity probe", () => {
        walls.SetParam("Comments", "%s-RB");
        throw new Exception("deliberate failure AFTER the write");
    });
} catch (Exception ex) {
    caught = true;
}
var dirty = walls.Where(x => x.GetStr("Comments") == "%s-RB").Count();
return "caught=" + caught + " dirty=" + dirty + " of " + walls.Count();
''' % (MARK, MARK), "P3 atomicity")

verdict("P3a. a failed transaction leaves NOTHING applied", out,
        want=["dirty=0 "],
        forbid=["NO EXCEPTION"])
# ⚠ Two-sided against the WRITE, not against a string: `caught=True` proves the throw
#   really happened after `SetParam` had run, and P4 below proves the same call applies
#   when nothing throws. Without both, "dirty=0" is also what a script that never wrote
#   would report.
verdict("P3b. ...and the throw really happened AFTER the write", out, want=["caught=True"])

# ---------------------------------------------------------------------------------
# 4. CONTROL — the same bulk write WITHOUT the throw must apply, or P3a is vacuous
# ---------------------------------------------------------------------------------
out = run(r'''
var walls = GetElements("Walls").Take(40).ToList();
walls.SetParam("Comments", "%s-OK");
var dirty = walls.Where(x => x.GetStr("Comments") == "%s-OK").Count();
return "dirty=" + dirty + " of " + walls.Count();
''' % (MARK, MARK), "P4 control")

verdict("P4. control — the same bulk write DOES apply when nothing throws", out,
        want=["dirty=40 of 40"])

# ---------------------------------------------------------------------------------
# 5. RESTORE — every wall back to its snapshot value, from the SESSION variable.
#
# ⚠ No id→value dictionary is rebuilt here any more: `__safeSnap` already holds all of
#   them in the REPL session, so nothing has to survive the reply's 40-line truncation.
#   The restore is asserted by COUNT (n must equal the snapshot size) and then by a
#   drift count computed IN C# — both are single numbers, so neither can be truncated.
# ---------------------------------------------------------------------------------
out = run(r'''
int n = 0;
foreach (var w in GetElements("Walls")) {
    string v;
    if (__safeSnap.TryGetValue(w.Id.Value, out v)) { w.SetVal("Comments", v); n++; }
}
Println("RESTORED=" + n);
Println("SNAPSHOT_SIZE=" + __safeSnap.Count);
''', "restore")

verdict("R0. restore addressed every snapshot wall", out,
        want=["RESTORED=%d" % snap_count])

# Verify by DRIFT COUNT computed in C# against the same session snapshot. A count is a
# single number, so the reply cannot truncate it into a false pass.
verify = run(r'''
int drift = 0;
int checked_ = 0;
var firstBad = "";
foreach (var w in GetElements("Walls")) {
    string v;
    if (!__safeSnap.TryGetValue(w.Id.Value, out v)) { continue; }
    checked_++;
    string nowv = w.GetStr("Comments");
    if (nowv != v) {
        drift++;
        if (firstBad == "") { firstBad = w.Id.Value + ": [" + v + "] -> [" + nowv + "]"; }
    }
}
Println("DRIFT=" + drift);
Println("CHECKED=" + checked_);
Println("FIRST_BAD=" + firstBad);
''', "verify restore")

print(verify.strip()[:300])

if "DRIFT=0" in verify and "CHECKED=%d" % snap_count in verify:
    results.append(("R1. every wall RESTORED to its snapshot", "PASS",
                    "%d wall(s) checked, 0 drift" % snap_count))
else:
    results.append(("R1. every wall RESTORED to its snapshot", "FAIL",
                    verify.strip()[:300]))

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
