#!/usr/bin/env python3
"""Probe: does the BULK OPERATION advisory fire on SINGLE-element writes?

Why this exists (2026-10-29, third release review; extended 2026-11-08)
------------------------------------------------------------------------
The reviewer's last open finding: a single `.Delete()` inside a `Transact` lambda printed

    BULK OPERATION DETECTED:
      • .Delete() — bulk delete on ALL filtered elements

for a delete of exactly ONE wall, because `Wall.Create(...)` was not recognised as a
single-element producer. Advisory only — it never blocks — but a warning that fires on
correct code trains the caller to skim past the ones that are right, and that is the same
failure class as the `has no spaces` note that was narrowed earlier.

⚠ F-2026-11-07-01 (2026-11-08). Three allow-list patches later the residual cases were
still there: an indexer, a field, a parameter, a differently-typed assignment. The rule was
INVERTED — an advisory is now emitted only when the receiver chain POSITIVELY proves a
collection; an unknown receiver is silent. The last four silent cases below are the repro
for that finding. Run this after ANY change to `bulk_operation_warnings()`: a detector that
simply stopped warning would still fail the "must still warn" half.

This probe is TWO-SIDED BY CONSTRUCTION. It runs OFFLINE against the shared core in
`paracore-mcp-core`, so it costs a second. ⚠ The core was split out of `paracore/mcp` in
v2.1.2, but `grpc_client.py` / `corescript_pb2*` still live in `paracore/mcp` — every
offline import needs BOTH paths. The old single path here made the probe exit FATAL
without testing anything at all.

Usage:
    mcp-build/.venv/Scripts/python.exe spikes/probe_bulk_warning.py
    (a bare `python` works too — the probe re-execs into that build venv if grpc is absent)
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent
ROOT = GEN.parent
CORE = ROOT / "paracore-mcp-core"
WIRE = ROOT / "paracore" / "mcp"

for p in (CORE, WIRE):
    if not p.is_dir():
        print(f"FATAL: shared core path not found: {p}")
        sys.exit(2)
if not (CORE / "mcp_core" / "tools.py").is_file():
    print(f"FATAL: mcp_core/tools.py not found under {CORE}")
    sys.exit(2)

# ⚠ A gate that cannot look must FAIL, not report green. Needing grpc is not a reason to
#   skip the probe — re-exec into the build venv that has the wire deps instead.
try:
    import grpc  # noqa: F401
except ImportError:
    venv = GEN / "mcp-build" / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if not venv.is_file():
        print(f"FATAL: grpc is missing and no build venv at {venv}")
        sys.exit(2)
    os.execv(str(venv), [str(venv), str(HERE / "probe_bulk_warning.py"), *sys.argv[1:]])

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(WIRE))
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

# ── MUST STAY SILENT: F-2026-11-07-01 residual cases ─────────────────────
# These are the shapes the old "warn unless proven single" allow-list could never
# enumerate. Under the inverted rule an UNKNOWN receiver is not claimed to be bulk.
check("indexer [0] -> .Hide() (one door)",
      'var doors = GetElements("Doors");\ndoors[0].Hide();',
      False)

check("method parameter -> .Hide() (one element)",
      'void One(Element e) { e.Hide(); }',
      False)

check("field -> .Delete() (one element)",
      'this._wall.Delete();',
      False)

check("unclassified assignment keyword -> .Isolate() (one element)",
      'List<Element> one = GetElements("Walls").First();\none.Isolate();',
      False)

# ── MUST STILL WARN: a proven collection ─────────────────────────────────
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

check("foreach over a proven collection still warns (bulk in scope)",
      'foreach (var e in GetElements("Walls")) { e.Delete(); }',
      True)

# ── a single element created AND a collection touched in the same script ──
check("single create + collection delete: warns exactly once",
      'var w = Wall.Create(Doc, curve, levelId, false);\nGetElements("Doors").Delete();',
      True)

fails = sum(1 for ok, _, _ in results if not ok)
print(f"\n{len(results) - fails}/{len(results)} passed, {fails} failure(s)")
sys.exit(0 if fails == 0 else 1)
