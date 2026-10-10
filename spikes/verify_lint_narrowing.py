"""
Probe: the FilteredElementCollector / get_Parameter lint narrowing (2026-10-02).

WHAT CHANGED
    _LINT_RULES previously matched `new FilteredElementCollector(` and `.get_Parameter(`
    unconditionally. Both fired on CORRECT family-authoring code:

      * GetElements<T>() has NO document overload — it always reads the ACTIVE document.
        Family work operates on a SECOND document, so the collector is the only option.
      * get_Parameter(BuiltInParameter.X) returns the Parameter OBJECT, which GetStr/GetNum
        cannot supply — and which family work needs for GetAssociatedFamilyParameter and
        AssociateElementParameterForParameter.

    A lint that fires on correct code trains the agent to ignore lints. Same failure class
    as D-MCP-2 (advice that cannot be followed).

WHY THIS PROBE ASSERTS THE CHOICE, NOT THE TOTAL
    A count of "how many lints fired" cannot distinguish "the rule was narrowed" from
    "the rule was deleted". Each case below is asserted by IDENTITY, in both directions:
    the exempt form must NOT fire, the flagged form MUST still fire.

Run:
    <managed python> spikes/verify_lint_narrowing.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from mcp_core.tool_helpers import (          # noqa: E402
    lint_paracore_conventions,
    check_paracore_compliance,
)

FAILURES = []


def case(name, code, *, must_fire, marker):
    """Assert by identity: `marker` present/absent in the lint text."""
    lint = lint_paracore_conventions(code) or ""
    fired = marker in lint
    ok = (fired == must_fire)
    status = "ok  " if ok else "FAIL"
    print(f"  [{status}] {name:<58} fired={fired}  want={must_fire}")
    if not ok:
        FAILURES.append(name)
        print(f"          lint was: {lint[:300]!r}")


print("FilteredElementCollector")
case("collector over a FAMILY doc  -> exempt",
     'var v = new FilteredElementCollector(famDoc).OfClass(typeof(Extrusion));',
     must_fire=False, marker="FilteredElementCollector")

case("collector over the ACTIVE doc -> still fires",
     'var v = new FilteredElementCollector(Doc).OfClass(typeof(Wall));',
     must_fire=True, marker="FilteredElementCollector")

case("collector with no argument -> still fires",
     'var v = new FilteredElementCollector().OfClass(typeof(Wall));',
     must_fire=True, marker="FilteredElementCollector")

print()
print("get_Parameter")
case("get_Parameter(BuiltInParameter.X) -> exempt",
     'var p = e.get_Parameter(BuiltInParameter.EXTRUSION_START_PARAM);',
     must_fire=False, marker="get_Parameter")

case('get_Parameter("Name") -> still fires',
     'var p = e.get_Parameter("Comments");',
     must_fire=True, marker="get_Parameter")

print()
print("Neither rule became a HARD error (must stay advisory)")

for name, code in [
    ("collector over active doc", 'var v = new FilteredElementCollector(Doc);'),
    ("get_Parameter by name",     'var p = e.get_Parameter("Comments");'),
]:
    hard = check_paracore_compliance(code)
    ok = hard is None
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name:<58} blocking={hard is not None}")
    if not ok:
        FAILURES.append(f"became blocking: {name}")

print()
print("Regression: the hard errors still block")
for name, code in [
    ("lowercase doc.",  'doc.Delete(id);'),
    ("AllElements",     'AllElements().Count();'),
    ("Transact(() =>",  'Transact(() => { });'),
]:
    hard = check_paracore_compliance(code)
    ok = hard is not None
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name:<58} blocking={ok}")
    if not ok:
        FAILURES.append(f"stopped blocking: {name}")

print()
print("Prose must not be blocked: the ENGLISH WORD 'document.' / 'doc.'")

for name, code, want_block in [
    ("comment ending in '...active document.'  -> must NOT block",
     '// always reads the ACTIVE document. In family work the collector is the only option.',
     False),
    ("comment ending in '...the doc.'         -> must NOT block",
     '// see the doc. Then proceed.',
     False),
    ("real access `document.SaveAs(path)`     -> MUST block",
     'document.SaveAs(path);', True),
    ("real access `doc.Delete(id)`            -> MUST block",
     'doc.Delete(id);', True),
]:
    hard = check_paracore_compliance(code)
    blocked = hard is not None
    ok = blocked == want_block
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
    if not ok:
        FAILURES.append(name)
        print(f"          got blocking={blocked}, want={want_block}")

print()
print("The shipped family template must itself be SUBMITTABLE")

# ⚠ The fixture is FAMILY code. It moved to the paracore-family MCP on 2026-10-10, when
#   this repo was stripped to the nine generalist method skills. Source it from the
#   sibling repo; SKIP — never FAIL — when that sibling is not checked out beside us.
#   (The lint RULES being proven still live HERE, in mcp_core/tool_helpers.py.)
TEMPLATE = (REPO.parent / "paracore-family" / "mcp_core" / "skills"
            / "family-authoring" / "build-template.cs")
if not TEMPLATE.is_file():
    print(f"  [SKIP] build-template.cs not found at {TEMPLATE}")
    print("         (check out paracore-family beside paracore-gen to run this check)")
else:
    tpl_code = TEMPLATE.read_text(encoding="utf-8")

    hard = check_paracore_compliance(tpl_code)
    if hard is None:
        print("  [ok  ] build-template.cs                      blocking=False")
    else:
        print("  [FAIL] build-template.cs                      blocking=True")
        print(f"          {hard[:600]}")
        FAILURES.append("template is blocked by the compliance layer")

    tpl_lint = lint_paracore_conventions(tpl_code)
    print(f"  [info] build-template.cs lint notes: {'none' if not tpl_lint else ''}")
    if tpl_lint:
        for line in str(tpl_lint).splitlines():
            if line.strip():
                print(f"          {line.strip()[:140]}")

print()
if FAILURES:
    print(f"VERDICT: {len(FAILURES)} FAILURE(S)")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("VERDICT: CLEAN — exemptions are by identity, both directions, nothing became blocking.")
