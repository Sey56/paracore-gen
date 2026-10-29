#!/usr/bin/env python3
"""Probe: does the BULK OPERATION advisory fire on SINGLE-element writes?

Why this exists (2026-10-29, third release review)
--------------------------------------------------
The reviewer's last open finding: a single `.Delete()` inside a `Transact` lambda printed

    BULK OPERATION DETECTED:
      • .Delete() — bulk delete on ALL filtered elements

for a delete of exactly ONE wall, because `Wall.Create(...)` was not recognised as a
single-element producer. Advisory only — it never blocks — but a warning that fires on
correct code trains the caller to skim past the ones that are right, and that is the same
failure class as the `has no spaces` note that was narrowed earlier.

This probe is TWO-SIDED BY CONSTRUCTION: every "must stay silent" case is paired with a
"must still warn" case, because a detector that simply stopped warning would pass half of
this file. It runs OFFLINE against `mcp_core.tools`, so it costs a second.

Usage:
    <python> spikes/probe_bulk_warning.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent
CORE = GEN.parent / "paracore" / "mcp"

if not (CORE / "mcp_core" / "tools.py").is_file():
    print(f"FATAL: shared core not found at {CORE}")
    sys.exit(2)

sys.path.insert(0, str(CORE))
from mcp_core.tools import bulk_operation_warnings  # noqa: E402

results = []


def check(label, code, expect_warn):
    warnings = bulk_operation_warnings(code)
    fired = bool(warnings)
    ok = fired == expect_warn
    results.append((ok, label, warnings))
    print(("PASS  " if ok else "FAIL  ") + label
          + ("" if ok else f"   <- expected warn={expect_warn}, got {warnings}"))


# ── MUST STAY SILENT: one element, created in place ───────────────────────
check("Wall.Create -> var -> .Delete() (the reviewer's case)",
      'Transact("mk", () => { var w = Wall.Create(Doc, curve, levelId, false); w.Delete(); });',
      False)

check("Wall.Create -> var -> .SetParam()",
      'var w = Wall.Create(Doc, curve, levelId, false);\nw.SetParam("Comments", "x");',
      False)

check("doc.Create.NewFamilyInstance -> var -> .Hide()",
      'var fi = Doc.Create.NewFamilyInstance(pt, sym, level, StructuralType.NonStructural);\nfi.Hide();',
      False)

check(".Duplicate() -> var -> .Delete()",
      'var copy = wall.Duplicate();\ncopy.Delete();',
      False)

check("GetElement(id).Delete() inline",
      'GetElement(359588).Delete();',
      False)

check("First().Hide() inline",
      'GetElements("Doors").First().Hide();',
      False)

# ── MUST STILL WARN: a collection ─────────────────────────────────────────
check("collection .Delete() still warns",
      'var walls = GetElements("Walls");\nwalls.Delete();',
      True)

check("inline collection .SetParam() still warns",
      'GetElements("Walls").SetParam("Comments", "x");',
      True)

check("filtered chain .Hide() still warns",
      'GetElements("Walls").Where(w => w.Name.Contains("PC")).Hide();',
      True)

check("GetElements(...).ToList().Delete() still warns",
      'GetElements("Walls").ToList().Delete();',
      True)

# ── a single element created AND a collection touched in the same script ──
check("single create + collection delete: warns exactly once",
      'var w = Wall.Create(Doc, curve, levelId, false);\nGetElements("Doors").Delete();',
      True)

fails = sum(1 for ok, _, _ in results if not ok)
print(f"\n{len(results) - fails}/{len(results)} passed, {fails} failure(s)")
sys.exit(0 if fails == 0 else 1)
