#!/usr/bin/env python3
"""Verify the RollbackNow outside-transaction honesty fix is LIVE on the installed engine.

THE DEFECT (old engine): a bare `Duplicate` outside any transaction created the type and
still threw; the reply said "The model is unchanged." — a false all-clear.

THE FIX (new engine, sha256 b63ee4d5…):
  `MightWrite` must recognise `Duplicate(` as a write verb, so the TransactionGroup opens;
  then `LooksLikeOutsideTransaction` must detect "outside of transaction" in the exception
  message and print "THE MODEL MAY HAVE CHANGED" instead of "The model is unchanged."

⚠⚠ CLEANUP BY ID-DIFFERENCE, NOT BY NAME. `Duplicate` outside a transaction creates the copy
   with the SOURCE type's name (measured 2026-10-29: id 972437 was named "Exterior - Brick on
   Mtl. Stud"). So a cleanup that looks for the name it passed in finds nothing. This probe
   snapshots the type ids BEFORE, then deletes whatever id APPEARED.

⚠ THIS PROBE WRITES: it creates one wall type and deletes it again. The delete is guarded
  (0 instances + the id did not exist before).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(WORKSPACE, "paracore-gen", "spikes"))

import _harness  # noqa: E402

t = _harness.boot()

results = []


def run(code, label="rollback-probe"):
    try:
        return t.execute_dynamic_query(code, label)
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else "   <- " + str(detail)))


# ── 1. Snapshot the type ids BEFORE ────────────────────────────────────────
snap = run(
    'var ids = string.Join(",", GetElements("WallTypes").Select(x => x.Id.Value.ToString()));\n'
    'Println("COUNT=" + GetElements("WallTypes").Count());\n'
    'Println("IDS=" + ids);'
)
print(snap)
m_count = re.search(r"COUNT=(\d+)", snap)
m_ids = re.search(r"IDS=([0-9,]+)", snap)
count_before = int(m_count.group(1)) if m_count else None
ids_before = set(m_ids.group(1).split(",")) if m_ids else None
check("baseline readable (count + ids)", count_before is not None and bool(ids_before),
      "could not parse COUNT/IDS")

# ── 2. The bare Duplicate — NO Transact wrapper ────────────────────────────
reply = run(
    'var wt = (WallType)GetElements("WallTypes").First();\n'
    'var dup = wt.Duplicate("PC-ROLLBACK-VERIFY");\n'
    'Println("SHOULD_NOT_REACH");'
)
print("\n--- error reply ---")
print(reply[:700])

# ── 3. The honesty assertions ─────────────────────────────────────────────
honest = "MODEL MAY HAVE CHANGED" in reply
dishonest = "model is unchanged" in reply.lower()
check("reply says 'THE MODEL MAY HAVE CHANGED' (honest sentence)", honest,
      "no honest sentence in reply")
check("reply does NOT say 'The model is unchanged' (false all-clear gone)", not dishonest,
      "false all-clear still present")
check("reply announces the rollback happened", "ROLLED BACK" in reply,
      "no 'ROLLED BACK' in reply")
check("reply names the failing line (debug-info fix)", "at your line 2" in reply,
      "no 'at your line 2' in reply")

# ── 4. Count AFTER — Revit applied part of the failed call ────────────────
after = run(
    'var ids = string.Join(",", GetElements("WallTypes").Select(x => x.Id.Value.ToString()));\n'
    'Println("COUNT=" + GetElements("WallTypes").Count());\n'
    'Println("IDS=" + ids);'
)
print(after)
m_count_a = re.search(r"COUNT=(\d+)", after)
m_ids_a = re.search(r"IDS=([0-9,]+)", after)
count_after = int(m_count_a.group(1)) if m_count_a else None
ids_after = set(m_ids_a.group(1).split(",")) if m_ids_a else None

check("wall-type count increased by exactly 1 (part of the call applied)",
      count_before is not None and count_after == count_before + 1,
      "before=%s after=%s" % (count_before, count_after))

new_ids = sorted(ids_after - ids_before) if (ids_after and ids_before) else []
check("exactly one NEW type id appeared", len(new_ids) == 1, "new_ids=%r" % (new_ids,))

# ── 5. Cleanup the new id, guarded ────────────────────────────────────────
if len(new_ids) == 1:
    target = new_ids[0]
    cleanup = run(
        'var dup = GetElements("WallTypes").FirstOrDefault(x => x.Id.Value == %s);\n'
        'if (dup == null) { Println("CLEANUP=already gone"); }\n'
        'else {\n'
        '    int n = dup.TypeInstanceCount();\n'
        '    if (n != 0) { throw new Exception("REFUSE: type %s has " + n + " instances"); }\n'
        '    Transact("delete rollback-probe leftover", () => { dup.Delete(); });\n'
        '    Println("CLEANUP=deleted %s");\n'
        '}' % (target, target, target)
    )
    print(cleanup)
    check("cleanup deleted the leftover type", "CLEANUP=deleted" in cleanup, cleanup[:300])

    final = run('Println("COUNT=" + GetElements("WallTypes").Count());')
    print(final)
    m_final = re.search(r"COUNT=(\d+)", final)
    check("wall-type count restored to baseline",
          m_final is not None and int(m_final.group(1)) == count_before,
          "baseline=%s final=%s" % (count_before, m_final.group(1) if m_final else "?"))
else:
    check("cleanup skipped — could not identify the leftover", False, "new_ids=%r" % (new_ids,))

print()
fails = sum(1 for ok, _ in results if not ok)
print("%d/%d passed, %d failure(s)" % (len(results) - fails, len(results), fails))
sys.exit(0 if fails == 0 else 1)
