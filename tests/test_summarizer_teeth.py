"""TEETH PROOF for tests/test_summarizer.py.

A test that has never failed has not been shown to test anything. This script
injects each pre-fix defect SEPARATELY, in memory, and records which tests go
red — so every fix can be attributed to a specific guard.

The source file is never modified. Each injection is reverted by reloading the
module, and a control run proves the suite is green on unmodified code.

Run:
    cd paracore-gen
    python tests/test_summarizer_teeth.py
"""


# ── the SHARED MCP CORE (`paracore/mcp`) — put it on sys.path ────────────────
# ⚠ It is not a per-repo package any more: it lives ONCE in the ENGINE repo and every MCP
#   imports it. See paracore/mcp/mcp_core/domain.py. Walk up to the sibling checkout.
import os as _os
import sys as _sys
if not getattr(_sys, "frozen", False):
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _dir, _core = _here, None
    for _ in range(6):
        if _os.path.isfile(_os.path.join(_dir, "paracore", "mcp", "mcp_core", "__init__.py")):
            _core = _os.path.join(_dir, "paracore", "mcp")
            break
        _up = _os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(
            "Paracore MCP shared core not found: no `paracore/mcp/mcp_core` above "
            f"{_here}. The core lives in the ENGINE repo, so the repos must be SIBLING "
            "checkouts under one parent directory."
        )
    _sys.path.insert(0, _core)
import contextlib
import importlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import mcp_core.summarizer as S

TEST_FILE = os.path.join(os.path.dirname(__file__), "test_summarizer.py")

# ── the pre-fix implementations, reproduced faithfully ────────────────────

PRE_FIX_KEYWORDS = {
    "area", "volume", "length", "weight", "mass", "count",
    "quantity", "total", "cost", "price", "tonnage",
    "amount", "perimeter", "girth",
}


def pre_fix_is_summable(header):
    """Defect 1: keyword allow-list only — no takeoff vocabulary, no suffix rule."""
    low = header.lower().strip()
    if low in S.NEVER_SUM:
        return False
    return any(kw in low for kw in PRE_FIX_KEYWORDS)


def pre_fix_is_numeric_column(data, header):
    """Defect 2: decide from data[0] alone."""
    sample = data[:1]
    if not sample:
        return False
    numeric = sum(1 for row in sample if S._to_float(row.get(header, "")) is not None)
    return numeric * 2 >= len(sample)


def pre_fix_no_aggregate_warning(headers, hidden):
    """Defect 3: say nothing."""
    return ""


def run_tests():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        pytest.main([TEST_FILE, "-q", "--no-header", "-p", "no:cacheprovider",
                     "--tb=no", "-rf"])
    out = buf.getvalue()
    failed = re.findall(r"^FAILED\s+(\S+)", out, flags=re.M)
    m = re.search(r"^(\d+ failed.*|\d+ passed.*)$", out, flags=re.M)
    return failed, (m.group(1) if m else "?")


def reload_module():
    global S
    S = importlib.reload(S)
    return S


def main():
    verdict = {}

    failed, summary = run_tests()
    print(f"[control] unmodified                 -> {summary}")
    verdict["control_green"] = not failed
    if failed:
        print("          FAILED:", *failed, sep="\n            ")

    # ── defect 1: the keyword allow-list gap ──────────────────────────────
    reload_module()
    S._is_summable = pre_fix_is_summable
    failed, summary = run_tests()
    print(f"[defect 1] SUM_KEYWORDS gap, no suffix -> {summary}")
    for t in failed:
        print("          red:", t)
    verdict["d1"] = failed

    # ── defect 2: sniff data[0] only ──────────────────────────────────────
    reload_module()
    S._is_numeric_column = pre_fix_is_numeric_column
    failed, summary = run_tests()
    print(f"[defect 2] sniff data[0] only          -> {summary}")
    for t in failed:
        print("          red:", t)
    verdict["d2"] = failed

    # ── defect 3: silent when there is no aggregate ───────────────────────
    reload_module()
    S._no_aggregate_warning = pre_fix_no_aggregate_warning
    failed, summary = run_tests()
    print(f"[defect 3] silent, no aggregate        -> {summary}")
    for t in failed:
        print("          red:", t)
    verdict["d3"] = failed

    reload_module()
    failed, summary = run_tests()
    print(f"[restored] reloaded from disk          -> {summary}")

    print()
    print("=" * 72)
    ok = (verdict["control_green"]
          and verdict["d1"] and verdict["d2"] and verdict["d3"]
          and not failed)
    print(f"control green ................... {verdict['control_green']}")
    print(f"defect 1 -> red ({len(verdict['d1'])} tests) ...... {bool(verdict['d1'])}")
    print(f"defect 2 -> red ({len(verdict['d2'])} tests) ...... {bool(verdict['d2'])}")
    print(f"defect 3 -> red ({len(verdict['d3'])} tests) ...... {bool(verdict['d3'])}")
    print(f"source restored to green ........ {not failed}")
    print(f"TEETH: {'PROVEN' if ok else 'NOT PROVEN'}")
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
