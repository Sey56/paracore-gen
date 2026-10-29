#!/usr/bin/env python3
"""Probe: the pipeline rewriter's position defect, LIVE on the installed engine.

Why this exists (2026-10-29)
----------------------------
`sb.Append(GetElements("Walls").Count())` failed to compile with

    error CS0411: The type arguments for method 'TrackEnumerable<T>' cannot be inferred

on legal code. `SemanticTrackingGuard` had ALREADY decided that `StringBuilder.Append`
must not be wrapped and recorded it as (SpanStart, name) in the original tree's
coordinates — but the rewriter looked that entry up with `node.SpanStart` AFTER
`base.VisitInvocationExpression(node)`, i.e. on a RECONSTRUCTED node that carries no
position in the original tree. The entry never matched and the wrap happened anyway.

Proven offline against two real artifacts (installed DLL fails, rebuilt DLL passes).
This probe proves the same thing through the shipped path: MCP -> gRPC -> engine.

⚠ TWO-SIDED BY CONSTRUCTION. A rewriter that stopped wrapping altogether would make
  R1 pass and silently kill every pipeline diagnostic, so R2 asserts a real pipeline
  still reports its stages. R3 covers the second defect in the same file (a comment
  above a wrapped call was emitted twice, which shifted every later diagnostic by one
  line per comment).

Usage:
    <python> spikes/probe_rewriter_live.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _harness  # noqa: E402

tools = _harness.boot()

results = []


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"   <- {detail}"))


def run(code, label):
    out = tools.execute_dynamic_query(code, f"probe_rewriter_live: {label}")
    return out or ""


# ── R1 — the CS0411 case, through the shipped path ────────────────────────
out = run(
    'var sb = new StringBuilder();\n'
    'sb.Append(GetElements("Walls").Count());\n'
    'Println("APPEND_OK " + sb.ToString());',
    "Append(pipeline)",
)
check("R1: sb.Append(pipeline) compiles and runs", "APPEND_OK" in out, out[:400])
check("R1: no CS0411 anywhere in the reply", "CS0411" not in out, out[:400])
check("R1: no TrackEnumerable mention in the reply", "TrackEnumerable" not in out, out[:400])

# ── R1b — the neighbours the reviewer proved legal ────────────────────────
out = run(
    'var sb2 = new StringBuilder();\n'
    'sb2.AppendLine(GetElements("Walls").Count().ToString());\n'
    'var joined = string.Join(",", new List<string>{"a","b"});\n'
    'Println("NEIGHBOURS_OK " + sb2.ToString().Trim() + " " + joined);',
    "AppendLine + string.Join",
)
check("R1b: AppendLine and string.Join still compile", "NEIGHBOURS_OK" in out, out[:400])

# ── R2 — CONTROL: a real pipeline must still report its stages ────────────
# ⚠ THE RENDERED TEXT IS THE WRONG THING TO ASSERT ON. The summarizer prints pipeline
# stages only when the script produced no other output, and a CONVENTION NOTE counts as
# output — so a healthy engine can render nothing. Ask the engine for the array instead.
sys.path.insert(0, str(Path(r"C://Users//seyou//Paracore//paracore//mcp")))
from grpc_client import execute_repl  # noqa: E402

r = execute_repl('GetElements("Walls").Take(3);', "probe-session")
diags = r.get("pipeline_diagnostics") or []
check("R2: pipeline diagnostics are still emitted", len(diags) >= 2, str(r)[:300])
check("R2: the first stage is the real source count", diags and diags[0] > 0, str(diags))
check("R2: the second stage is the Take count", len(diags) >= 2 and diags[1] == 3, str(diags))

# ── R3 — line numbers survive comments above a wrapped call ───────────────
code = (
    "// first comment\n"
    "// second comment\n"
    "var z = 1;\n"
    "var boom = z / (z - 1);\n"
    "Println(boom);"
)
out = run(code, "line drift")
check("R3: the runtime error names the USER's line 4",
      "line 4" in out, out[:600])
check("R3: it does not name line 5 or 6",
      "line 5" not in out and "line 6" not in out, out[:600])

# ── R4 — a compile error with comments above it lands on the real line ────
code = (
    "// alpha\n"
    "// beta\n"
    "var w = GetElements(\"Walls\").Where(w => w.Id != null).First();\n"
    "var bad = NoSuchMethodAtAll(w);\n"
)
out = run(code, "compile error drift")
check("R4: the compile error names line 4",
      "line 4" in out, out[:600])

fails = sum(1 for ok, _ in results if not ok)
print(f"\n{len(results) - fails}/{len(results)} passed, {fails} failure(s)")
sys.exit(0 if fails == 0 else 1)
