#!/usr/bin/env python3
"""Compile-truth probe for the "Native Properties" block in the skills.

WHY (2026-10-29, fifth review). Two skill files told the agent:

    el.Symbol   → ElementId
    el.Area     → double (ft²)
    el.Volume   → double (ft³)

All three are wrong. `Symbol` is a `FamilyInstance` member returning a `FamilySymbol`,
and `Area`/`Volume` are not members of `Element` at all — they exist on `Room`/`Space`
and, for every other element, only as PARAMETERS reached through `GetNum`/`GetVal`.
An agent that believes the doc writes `el.Area` and gets `CS1061`, then either burns a
turn guessing or "fixes" it with `dynamic` — which the tool blocks.

⚠ THE POINT OF THIS FILE IS THE METHOD, NOT THE ANSWERS. Reading the Revit API
  reference would have told me the same thing, and I had already been wrong about it
  once. A snippet is decided by the COMPILER, so the compiler is asked directly: each
  case is wrapped in `if (x != null)` so it is type-checked but never executed — no
  element needs to exist, and nothing is touched.

⚠ TWO-SIDED. Proving `el.Area` fails is worthless on its own: a probe that only tests
  things that must fail passes even if the engine cannot compile anything at all. Every
  "must fail" case is paired with a "must compile" case (`el.Id`, `el.Name`, `el.Location`,
  `fi.Symbol`, `room.Area`) so a blanket breakage shows up as a failure here.

Usage:
    <venv-python> spikes/probe_native_props.py
Requires Revit open with a document loaded (ping must report connected).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _harness  # noqa: E402

t = _harness.boot()

results = []          # (label, status, detail)


def case(label, code, must_compile):
    """Submit `code`; PASS when its compilability matches `must_compile`."""
    try:
        out = t.execute_dynamic_query(code, "native-prop probe")
    except Exception as exc:                                    # noqa: BLE001
        results.append((label, "RAISED", "%s: %s" % (type(exc).__name__, exc)))
        return
    flat = " ".join(out.split())
    compiled = "error CS" not in out
    # ⚠ Show the DIAGNOSTIC, not the whole output. A "must not compile" case passes on
    #   ANY error, so a typo in the snippet would pass it for the wrong reason; the
    #   error code is the only thing that distinguishes CS1061 (no such member) from a
    #   mistake in the probe itself.
    diag = ""
    for tok in flat.split():
        # ⚠ The code arrives as `CS1061:` — WITH the colon. The first version of this
        #   line tested `tok[2:].isdigit()`, which is False for "1061:", so `diag` stayed
        #   empty and every case printed the label "compiled" — including the three that
        #   had just failed to compile. The PASS/FAIL column was correct throughout; the
        #   evidence beside it was a lie, which is worse, because that is the part a human
        #   reads. Strip the punctuation before asking whether it is a number.
        if tok.startswith("CS") and tok[2:].rstrip(":;,.)").isdigit():
            diag = tok.rstrip(":;,.)")
            break
    if compiled == must_compile:
        shown = diag if diag else ("compiled" if compiled else "failed, no CS code found")
        results.append((label, "PASS", shown + "  " + flat[:80]))
    elif must_compile:
        results.append((label, "FAIL", "should compile, did not | %s" % flat[:170]))
    else:
        results.append((label, "FAIL", "should NOT compile, did | %s" % flat[:170]))


# --- must NOT compile: the three false lines -------------------------------------
case("Element.Area is not a member",
     'Element el = null; if (el != null) { var a = el.Area; return "x"; } return "y";',
     must_compile=False)

case("Element.Volume is not a member",
     'Element el = null; if (el != null) { var v = el.Volume; return "x"; } return "y";',
     must_compile=False)

case("Element.Symbol is not a member",
     'Element el = null; if (el != null) { var s = el.Symbol; return "x"; } return "y";',
     must_compile=False)

# --- must compile: the surviving native properties -------------------------------
case("Element.Id compiles",
     'Element el = null; if (el != null) { ElementId i = el.Id; return "x"; } return "y";',
     must_compile=True)

case("Element.Name compiles",
     'Element el = null; if (el != null) { string n = el.Name; return "x"; } return "y";',
     must_compile=True)

case("Element.Location compiles",
     'Element el = null; if (el != null) { Location l = el.Location; return "x"; } return "y";',
     must_compile=True)

# --- the correct homes for the three false lines ---------------------------------
case("FamilyInstance.Symbol compiles AND is a FamilySymbol",
     'FamilyInstance fi = null; if (fi != null) { FamilySymbol s = fi.Symbol; return "x"; } return "y";',
     must_compile=True)

case("Room.Area compiles",
     'Room rm = null; if (rm != null) { double a = rm.Area; return "x"; } return "y";',
     must_compile=True)

case("Room.Volume compiles",
     'Room rm = null; if (rm != null) { double v = rm.Volume; return "x"; } return "y";',
     must_compile=True)

# --- the universal route for area/volume on any element ---------------------------
case("GetNum(Area) works on a non-room element",
     'var w = GetElements("Walls").First(); return "A=" + w.GetNum("Area");',
     must_compile=True)

print()
width = max(len(r[0]) for r in results)
fails = 0
for label, status, detail in results:
    if status != "PASS":
        fails += 1
    print("%-*s  %-6s  %s" % (width, label, status, detail))
print()
print("%d passed, %d failed" % (len(results) - fails, fails))
sys.exit(1 if fails else 0)
