#!/usr/bin/env python3
"""
Probe ROUND 30 — the three fixes from this round:
  1. Runtime error line numbers (WithEmitDebugInformation + DescribeRuntimeLocation)
  2. All-or-nothing transaction envelope (ScriptRunScope)
  3. Transaction granularity advisory on the REPL path (TransactionGranularityAdvisory)
  Plus: the double-wrap "Did you mean" fix.
"""
import sys, os, re, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
import _harness

def run(code, label):
    t = _harness.boot(start_watcher=False)
    return t.execute_dynamic_query(code, label)

results = []

def verdict(label, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((label, tag, detail))
    print(f"  {tag}  {label}  {detail[:100]}")

print("=== R1. Runtime error line number ===")
out = run('int a = 5;\nint b = 0;\nint c = a / b;\nreturn "c=" + c;', 'R1 divide-by-zero')
flat = " ".join(out.split())
verdict("R1a. divide-by-zero names the line",
        "at your line" in flat and "3" in flat,
        flat[:160])
verdict("R1b. the error type is still there",
        "divide by zero" in flat.lower(),
        flat[:120])

print("\n=== R2. All-or-nothing envelope ===")
# First snapshot the door's Comments
snap = run(r'''
var d = GetElements<FamilyInstance>("Doors").FirstOrDefault();
return d == null ? "NO DOORS" : d.GetStr("Comments");
''', 'R2 snapshot')
print("  door Comments before:", repr(snap.strip())[:60])

# Write + throw — the envelope MUST roll back
out = run(r'''
var d = GetElements<FamilyInstance>("Doors").FirstOrDefault();
d.SetVal("Comments", "ENVELOPE-TEST");
throw new Exception("deliberate failure AFTER write");
''', 'R2 write+throw')
flat = " ".join(out.split())
verdict("R2a. failure is reported",
        "deliberate failure" in flat,
        flat[:120])
verdict("R2b. rollback is announced",
        "ROLLED BACK" in flat or "rolled back" in flat.lower(),
        flat[:160])

# Verify the write was undone
after = run(r'''
var d = GetElements<FamilyInstance>("Doors").FirstOrDefault();
return d == null ? "NO DOORS" : d.GetStr("Comments");
''', 'R2 verify')
print("  door Comments after:", repr(after.strip())[:60])
verdict("R2c. the write was undone (Comments restored)",
        "ENVELOPE-TEST" not in after,
        f"before={snap.strip()[:30]} after={after.strip()[:30]}")

print("\n=== R3. Transaction granularity advisory on REPL path ===")
out = run(r'''
foreach (var w in GetElements("Walls")) { w.SetVal("Comments", "GRAN-TEST"); }
return "ok";
''', 'R3 loop-write')
flat = " ".join(out.split())
verdict("R3a. advisory fires for loop write without Transact",
        "TRANSACTION GRANULARITY" in flat,
        flat[:160])
verdict("R3b. advisory names the line",
        "line " in flat,
        flat[:120])

# Restore
run(r'foreach (var w in GetElements("Walls")) { w.SetVal("Comments", ""); }', 'R3 restore')

# False positive must NOT fire
out2 = run(r'''
var n = 0;
foreach (var w in GetElements("Walls")) { n++; }
GetElements("Walls").First().SetVal("Comments", "FP-TEST");
return "n=" + n;
''', 'R3 false-positive check')
flat2 = " ".join(out2.split())
verdict("R3c. NO advisory for read-only loop + write OUTSIDE it",
        "TRANSACTION GRANULARITY" not in flat2,
        flat2[:120])
# Clean up
run(r'GetElements("Walls").First().SetVal("Comments", "");', 'R3 cleanup FP')

print("\n=== R4. Double-wrap 'Did you mean' fix ===")
out = run(r'GetElements("Walls").First().SetVal("Fire Raitng", "x");', 'R4 typo')
flat = " ".join(out.split())
# The OLD bug: Did you mean " Did you mean "Fire Rating"?"?
# The FIX: Did you mean "Fire Rating"?  (single)
has_double = 'Did you mean " Did you mean' in flat
has_single = 'Did you mean "Fire Rating"' in flat and 'Did you mean " Did you mean' not in flat
verdict("R4a. suggestion is NOT double-wrapped",
        not has_double,
        flat[:160])
verdict("R4b. suggestion IS present (single wrap)",
        has_single,
        flat[:120])

print("\n=== SUMMARY ===")
passed = sum(1 for _, t, _ in results if t == "PASS")
failed = sum(1 for _, t, _ in results if t == "FAIL")
print(f"{passed} passed, {failed} failed, {len(results)} total")
if failed:
    print("\nFAILURES:")
    for label, tag, detail in results:
        if tag == "FAIL":
            print(f"  {label}: {detail[:200]}")
