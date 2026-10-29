#!/usr/bin/env python3
"""Can the security scan be defeated by QUALIFYING the type name?

THE WEAKNESS (found 2026-10-29). Every constructor pattern in the scan was anchored as

    new\\s+<Type>\\s*\\(

which requires the type name to follow `new` with only whitespace between. So
`new Thread(` was refused and `new System.Threading.Thread(` was NOT — measured, the latter
EXECUTED. `new Autodesk.Revit.DB.Transaction(` walked past the read-only guard for the same
reason.

⚠⚠ WHICH LAYER OWNS WHICH TYPE — the first version of this probe got this wrong and reported
   four "holes" that were not holes:

   * `explore_revit_data` (READ-ONLY) must refuse Transaction / TransactionGroup /
     SubTransaction, because the whole point of that tool is discovery.
   * `execute_dynamic_query` (WRITE) must NOT refuse them. A raw `new Transaction(Doc)` is a
     legal way for a script to group its own writes — Paracore's `Transact()` is a wrapper
     around exactly that. Refusing it there would break correct code.
   * `Thread` is refused on the AGENT path (`_BLOCKED_AGENT_ONLY`), never on the read-only
     path alone, because a background thread is not a model change.

   The control case below is what caught this: `new Transaction(Doc)` unqualified is the form
   the scan was written for, and it is legitimately ALLOWED by execute_dynamic_query. A probe
   whose control fails is a probe with a wrong expectation, not a product with a bug.

⚠ HARMLESS IF EXECUTED: constructors are only CONSTRUCTED (never `.Start()`ed except in the
  containment case, which is the point of that case), and the StreamWriter targets a directory
  that does not exist so it throws instead of creating a file.
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


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else "   <- " + str(detail)))


def run(code, label="bypass"):
    try:
        return t.execute_dynamic_query(code, label)
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def explore(code, label="bypass-explore"):
    try:
        return t.explore_revit_data(code, "probe: containment test", session_id="mcp-session")
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def refused(out):
    """True when the call was refused rather than executed.

    ⚠ Anchored on the refusal WORDING, not on the absence of "RAN": a refusal that still
    reached the engine would otherwise be scored as a pass.
    """
    low = out.lower()
    markers = ("refus", "not allowed", "blocked", "violation", "forbidden",
               "disallowed", "not permitted", "dangerous pattern", "read-only")
    return any(m in low for m in markers)


def executed(out):
    return "RAN" in out


# ── AGENT PATH: these constructors must be refused by check_dangerous_patterns ──
AGENT_CASES = [
    ("Thread",       'var x = new System.Threading.Thread(() => { }); Println("RAN");'),
    ("HttpClient",   'var x = new System.Net.Http.HttpClient(); Println("RAN");'),
    ("Socket",       'var x = new System.Net.Sockets.Socket(1, 1, 1); Println("RAN");'),
    # A path in a directory that does not exist: if this ever executes it throws, so the
    # probe cannot create a file as a side effect of a scan hole.
    ("StreamWriter", 'var x = new System.IO.StreamWriter("Z:\\\\__no_such_dir__\\\\p.txt"); Println("RAN");'),
    ("Process",      'System.Diagnostics.Process.Start("cmd.exe"); Println("RAN");'),
    ("ProcessStartInfo", 'var x = new System.Diagnostics.ProcessStartInfo("cmd.exe"); Println("RAN");'),
]

print("=" * 78)
print("AGENT PATH — a qualified constructor must be refused")
print("=" * 78)
holes = []
for label, code in AGENT_CASES:
    out = run(code)
    ok = refused(out) and not executed(out)
    if not ok:
        holes.append(label)
    check(f"refused: new ...{label}(...)", ok, out.strip()[:160])

# ── AGENT PATH CONTROL: the unqualified forms the scan was written for ─────────
print()
print("=" * 78)
print("AGENT PATH CONTROL — unqualified forms")
print("=" * 78)
for label, code in (("Thread", 'var x = new Thread(() => { }); Println("RAN");'),
                    ("HttpClient", 'var x = new HttpClient(); Println("RAN");')):
    out = run(code)
    check(f"refused (control): new {label}(...)", refused(out) and not executed(out),
          out.strip()[:160])

# ── WRITE PATH CONTROL: a raw transaction is LEGAL here, and must stay legal ──
print()
print("=" * 78)
print("WRITE PATH — a raw transaction is legal and must NOT be refused")
print("=" * 78)
out = run('var tx = new Autodesk.Revit.DB.Transaction(Doc); Println("RAN CONSTRUCTED " + (tx != null));')
check("allowed: new Autodesk.Revit.DB.Transaction(Doc) in execute_dynamic_query",
      executed(out) and not refused(out), out.strip()[:200])
out = run('var tx = new Transaction(Doc); Println("RAN CONSTRUCTED " + (tx != null));')
check("allowed (control): new Transaction(Doc) in execute_dynamic_query",
      executed(out) and not refused(out), out.strip()[:200])

# ── READ-ONLY PATH: the guard must name the write, not stay silent ────────────
print()
print("=" * 78)
print("READ-ONLY PATH — a qualified raw transaction must be REFUSED")
print("=" * 78)
for label, code in (
        ("Transaction", 'var tx = new Autodesk.Revit.DB.Transaction(Doc); Println("RAN");'),
        ("TransactionGroup", 'var tg = new Autodesk.Revit.DB.TransactionGroup(Doc, "p"); Println("RAN");'),
        ("SubTransaction", 'var st = new Autodesk.Revit.DB.SubTransaction(Doc); Println("RAN");'),
        ("Transaction (unqualified control)", 'var tx = new Transaction(Doc); Println("RAN");')):
    out = explore(code)
    check(f"refused in explore: {label}", refused(out) and not executed(out), out.strip()[:200])

# ⚠ And the guard must NOT fire on a comment that merely mentions the call — the same
#   "scan code, not prose" rule the other list already follows.
out = explore('// never do new Transaction(Doc) inside a read-only snippet\n'
              'Println("PROSE_OK " + GetElements("Walls").Count());')
check("a comment naming a write does not refuse a correct query",
      "PROSE_OK" in out and not refused(out), out.strip()[:200])

# ── THE HIGH-VALUE CASE: does layer 2 contain a qualified raw transaction? ──
print()
print("=" * 78)
print("CONTAINMENT — a write reached by any route is discarded")
print("=" * 78)

MARK = "PC-BYPASS-LEAK"


def dirty():
    out = run('Println("DIRTY=" + GetElements("Walls").Where(x => x.GetStr("Comments")'
              '.StartsWith("%s")).Count());' % MARK)
    m = re.search(r"DIRTY=(\d+)", out)
    return int(m.group(1)) if m else None


dirty_before = dirty()

# The qualified constructor, then a REAL write inside it. The scan now refuses this, so the
# payload is also reachable only if the scan is defeated — which is exactly what we want to
# keep proving. If the refusal fires, nothing runs and nothing leaks.
payload = (
    'var tx = new Autodesk.Revit.DB.Transaction(Doc);\n'
    'tx.Start();\n'
    'GetElements("Walls").First().SetVal("Comments", "%s");\n'
    'tx.Commit();\n'
    'Println("WROTE");' % MARK
)
out = explore(payload)
print(out.strip()[:400])

dirty_after = dirty()

check("a qualified raw Transaction does not leave a write behind",
      dirty_after == 0, "DIRTY=%r — the write LEAKED past the rollback group" % (dirty_after,))
check("baseline was clean before the attempt", dirty_before == 0,
      "DIRTY=%r before" % (dirty_before,))

print()
fails = sum(1 for ok, _ in results if not ok)
if holes:
    print("SCAN HOLES (qualified form not refused): " + ", ".join(holes))
print("=" * 78)
print("%d/%d passed, %d failure(s)" % (len(results) - fails, len(results), fails))
print("=" * 78)
sys.exit(0 if fails == 0 else 1)
