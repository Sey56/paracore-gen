#!/usr/bin/env python3
"""
Probe a paracore-mcp exe over stdio: list its tools (names AND descriptions), and read
the skill resources it will actually serve.

Why behavioural and not extraction
----------------------------------
`mcp_server.py` and `mcp_core/tools.py` are compiled into the exe's PYZ, so
`CArchiveReader` cannot see them (it reads `datas` only). Asking the exe itself is
the only honest check — and `resources/read` is the strongest one available offline:
it proves the text an agent will be handed, not merely that a build ran.

⚠ A tool DESCRIPTION is an instruction surface too — it is what the agent reads about
the tool before calling it. On 2026-10-07 the belief "A plan view is unaffected [by
annotation]" was corrected in the skill and in EXTENSION_METHODS.md, but survived in the
`export_view` docstring, and only the live `tools/list` surfaced it. So the descriptions
are asserted here, both ways: the new text must be present AND the stale text absent.

Usage:
    <python> spikes/probe_installed_tools.py [path\\to\\paracore-mcp.exe]
Default path is the INSTALLED exe.
"""
import json
import subprocess
import sys
import threading
import time

EXE = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\seyou\AppData\Roaming\paracore-data\mcp-servers\paracore-mcp.exe"

EXPECT_TOOLS = ["ping", "get_context", "pick_object", "export_view",
                "_explore_revit_data", "_execute_dynamic_query",
                "_search_schema", "_read_extension_methods"]

SKILLS_TO_READ = {
    "skill://project-modeling/SKILL.md": ["closure gap", "Doc.GetWarnings()", "Step 0",
                                          "NewRooms2"],
    "skill://massing-forms/SKILL.md": ["CONCEPT STUDIES ONLY"],
    "skill://create-geometry/SKILL.md": ["project-modeling"],
    "skill://display-visualize/SKILL.md": ["export_view(", "annotations"],
    "skill://annotations-dimensions/SKILL.md": ["AnyModelDirection", "ValueString",
                                                "NewRooms2", "DimensionSegment"],
}

# Two-sided, per tool. A one-sided check cannot tell "corrected" from "deleted".
# ⚠ Updated 2026-10-08: export_view gained the `annotations` mode, so the OLD assertions
#   ('SUPPRESSED', 'shrink the subject', 'hideAnnotation: false') are now the stale text and
#   moved to MUST_NOT_CONTAIN. A probe that keeps asserting a replaced contract reports a
#   correct product as broken.
TOOL_DESC_MUST_CONTAIN = {
    "export_view": ["annotations", '"tags"', '"model"', "datum"],
}
TOOL_DESC_MUST_NOT_CONTAIN = {
    "export_view": ["A plan view is unaffected", "hideAnnotation: false", "SUPPRESSED"],
}

# Behavioural: the compile-error annotator. Needs Revit reachable; degrades to SKIP if not.
ERROR_PROBE_CODE = ('var __t = new StringBuilder();\n'
                    '__t.AppendLine("probe");\n'
                    'Println(__undefinedProbeSymbol);\n')

failures = []
skips = []
checks = 0


def check(name, cond, detail=""):
    global checks
    checks += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"   {detail}" if not cond else ""))
    if not cond:
        failures.append(name)


def skip(name, why):
    skips.append(name)
    print(f"  [SKIP] {name}   {why}")


def reader(proc, out, logs):
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logs.append(line)


def send(proc, obj):
    proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
    proc.stdin.flush()


def wait_for(msgs, want_id, timeout=120.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for m in msgs:
            if m.get("id") == want_id:
                return m
        time.sleep(0.05)
    return None


def main():
    print(f"exe: {EXE}")
    proc = subprocess.Popen([EXE], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    msgs, logs = [], []
    threading.Thread(target=reader, args=(proc, msgs, logs), daemon=True).start()

    send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "tools-probe", "version": "1.0"}}})
    if wait_for(msgs, 1, timeout=150.0) is None:
        print("FATAL: no initialize response")
        print("stderr tail:", "".join(logs[-20:]))
        proc.kill()
        return 2
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    print("\n== tools/list ==")
    send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    resp = wait_for(msgs, 2)
    names, descs = [], {}
    if resp:
        for t in resp.get("result", {}).get("tools", []):
            names.append(t.get("name"))
            descs[t.get("name")] = t.get("description") or ""
    print(f"  tools ({len(names)}): {sorted(names)}")
    for t in EXPECT_TOOLS:
        check(f"tool '{t}' is exposed", t in names)

    print("\n== tool DESCRIPTIONS — the text the agent reads about each tool ==")
    # ⚠ Case-insensitive: these are PROSE. The docstring emphasises with capitals
    # ("SHRINK the subject"), so a case-sensitive assert on lower-case text fails on
    # correct content — a probe bug, not a product one.
    for tool, phrases in TOOL_DESC_MUST_CONTAIN.items():
        d = descs.get(tool, "")
        check(f"{tool} description non-empty", bool(d), f"len={len(d)}")
        for p in phrases:
            check(f"  {tool} description contains {p!r}", p.lower() in d.lower())
    for tool, phrases in TOOL_DESC_MUST_NOT_CONTAIN.items():
        d = descs.get(tool, "")
        for p in phrases:
            check(f"  {tool} description does NOT contain {p!r}", p.lower() not in d.lower())

    print("\n== resources/read — what the agent will actually be handed ==")
    rid = 100
    for uri, phrases in SKILLS_TO_READ.items():
        send(proc, {"jsonrpc": "2.0", "id": rid, "method": "resources/read",
                    "params": {"uri": uri}})
        r = wait_for(msgs, rid)
        rid += 1
        text = ""
        if r and "result" in r:
            for c in r["result"].get("contents", []):
                text += c.get("text", "")
        check(f"{uri} served", bool(text), f"len={len(text)}")
        for p in phrases:
            check(f"  contains {p!r}", p in text)

    # ── Behavioural: does the shipped exe actually ANNOTATE a compile failure? ──
    # `tool_helpers.py` is compiled into the PYZ, so extraction cannot see it and
    # `tools/list` only proves the description. Driving the tool with a snippet that
    # cannot compile is the only offline check that proves the annotator shipped.
    # ⚠ Needs the in-Revit engine on localhost:50051 — SKIP, never FAIL, when it is down.
    print("\n== behavioural — the compile-error annotator (needs Revit up) ==")
    send(proc, {"jsonrpc": "2.0", "id": 300, "method": "tools/call",
                "params": {"name": "_explore_revit_data",
                           "arguments": {"csharp_code": ERROR_PROBE_CODE,
                                         "justification": "probe: compile-error annotator"}}})
    r = wait_for(msgs, 300)
    text = ""
    if r and "result" in r:
        for c in r["result"].get("content", []):
            text += c.get("text", "")
    if not text:
        skip("compile-error annotator", "no tool response")
    elif "NO CONNECTION TO REVIT" in text or "Could not read" in text:
        skip("compile-error annotator", "Revit not reachable")
    else:
        # The snippet fails on line 3 — the annotator must map it back AND quote the
        # source, which is the whole point of the fix.
        #
        # ⚠ The header names which coordinate system the ENGINE reported in, and
        # that depends on which engine build is installed in Revit — a file copy
        # that is a separate act from installing this MCP. Both forms are correct:
        #   legacy engine -> "(5,3): error CS0103: …"  and the annotator says
        #                    "prepends 2 lines"
        #   fixed engine  -> "script(3,3): error CS0103: …" and the annotator says
        #                    "in YOUR coordinates"
        # Asserting only one form would turn a legitimate engine upgrade into a
        # probe failure.
        check("annotator maps the line back", "your line 3" in text, text[:300])
        check("annotator quotes the source line",
              "__undefinedProbeSymbol" in text, text[:300])
        check("annotator states which coordinate system the engine used",
              ("prepends 2 lines" in text) or ("in YOUR coordinates" in text), text[:300])
        check("annotator names the error code", "CS0103" in text, text[:300])

    proc.kill()
    print("\n" + "=" * 60)
    print(f"{checks - len(failures)}/{checks} checks passed"
          + (f"   ({len(skips)} skipped)" if skips else ""))
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
