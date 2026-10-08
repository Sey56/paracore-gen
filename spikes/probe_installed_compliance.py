#!/usr/bin/env python3
"""
Probe the INSTALLED paracore-mcp.exe's compliance checker over stdio JSON-RPC.

Why this exists
---------------
`mcp_core/tool_helpers.py` is compiled into the exe's PYZ, so it is NOT visible to
`PyInstaller.archive.readers.CArchiveReader` (that sees `datas` only). Extraction
therefore cannot prove whether the D-MCP-6 / D-MCP-7 fixes reached the frozen build.

The honest alternative is BEHAVIOURAL: drive the installed exe as an MCP server and
ask it to validate code whose verdict DIFFERS between the old and new checker. The
compliance gate runs BEFORE any gRPC call to Revit (tools.py:197), so these probes
are decisive whether or not Revit is connected.

Probes
------
  P1  prose containing the English word "document."      expect: NOT blocked   (D-MCP-6)
  P2  a REAL `document.SaveAs(...)` member access        expect: BLOCKED       (control)
  P3  `new FilteredElementCollector(Doc)`                expect: lint w/ new text (D-MCP-7)
  P4  `new FilteredElementCollector(famDoc)`             expect: NO collector lint (D-MCP-7)
  P5  `el.get_Parameter("Name")`                         expect: lint         (D-MCP-7)
  P6  `el.get_Parameter(BuiltInParameter.X)`             expect: NO get_Parameter lint (D-MCP-7)

Run:  <managed python> spikes/probe_installed_compliance.py
"""
import json
import subprocess
import sys
import threading
import time

EXE = r"C:\Users\seyou\AppData\Roaming\paracore-data\mcp-servers\paracore-mcp.exe"

# Text that only the NEW checker emits / must no longer emit.
NEW_LINT_MARKER = "A collector over another document"   # D-MCP-7 collector narrowing
OLD_BLOCK_MARKER = "only the injected global exists"    # the D-MCP-6 hard error, still armed


def rpc_reader(proc, out, err):
    """Read newline-delimited JSON-RPC from the server; skip non-JSON log lines."""
    for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            err.append(line)   # a log line, not a response


def send(proc, obj):
    proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
    proc.stdin.flush()


def wait_for(msgs, want_id, timeout=90.0):
    """Block until a response with the given id arrives. Returns it or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for m in msgs:
            if m.get("id") == want_id:
                return m
        time.sleep(0.05)
    return None


def call_tool(proc, msgs, req_id, name, arguments):
    send(proc, {"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
                "params": {"name": name, "arguments": arguments}})
    resp = wait_for(msgs, req_id)
    if resp is None:
        return None
    res = resp.get("result", {})
    content = res.get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", "")
    return json.dumps(res)


def main():
    proc = subprocess.Popen(
        [EXE],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    msgs, logs = [], []
    t = threading.Thread(target=rpc_reader, args=(proc, msgs, logs), daemon=True)
    t.start()

    # ── handshake ─────────────────────────────────────────────────────────
    send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "compliance-probe", "version": "1.0"}}})
    if wait_for(msgs, 1, timeout=120.0) is None:
        print("FATAL: no initialize response (server did not start)")
        print("stderr tail:", "".join(logs[-20:]))
        proc.kill()
        return 2
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    probes = [
        ("P1  prose with the English word 'document.'  -> expect NOT blocked",
         "// Probe A: this snippet reads the ACTIVE document. In family work we use famDoc.\n"
         "// Nothing here touches a project document.\nDoc.Title",
         "not_blocked"),
        ("P2  real `document.SaveAs(...)` member access -> expect BLOCKED",
         '// Probe B control: a real member access on the undefined lowercase global.\n'
         'document.SaveAs("C:\\\\temp\\\\x.rfa")',
         "blocked"),
        ("P3  new FilteredElementCollector(Doc)         -> expect NEW lint text",
         "new FilteredElementCollector(Doc).ToElements()",
         "lint_new"),
        ("P4  new FilteredElementCollector(famDoc)      -> expect NO collector lint",
         "new FilteredElementCollector(famDoc).ToElements()",
         "no_collector_lint"),
        ("P5  el.get_Parameter(\"Name\")                  -> expect lint",
         'el.get_Parameter("Name")',
         "lint_getparam"),
        ("P6  el.get_Parameter(BuiltInParameter.X)      -> expect NO get_Parameter lint",
         "el.get_Parameter(BuiltInParameter.EXTRUSION_START_PARAM)",
         "no_getparam_lint"),
    ]

    results = []
    rid = 10
    for label, code, kind in probes:
        text = call_tool(proc, msgs, rid, "_explore_revit_data",
                         {"csharp_code": code, "justification": "compliance probe"})
        rid += 1
        results.append((label, kind, text))

    # ── verdicts ──────────────────────────────────────────────────────────
    print("=" * 78)
    print("INSTALLED EXE COMPLIANCE PROBES  —", EXE)
    print("=" * 78)
    all_ok = True
    for label, kind, text in results:
        if text is None:
            print(f"[FAIL] {label}\n        no response")
            all_ok = False
            continue
        blocked = "cannot run" in text
        has_new_lint = NEW_LINT_MARKER in text
        has_old_block = OLD_BLOCK_MARKER in text
        has_collector_lint = "FilteredElementCollector" in text and "instead of new FilteredElementCollector" in text
        has_getparam_lint = "instead of .get_Parameter" in text

        if kind == "not_blocked":
            ok = not blocked
        elif kind == "blocked":
            ok = blocked and has_old_block
        elif kind == "lint_new":
            ok = has_collector_lint and has_new_lint
        elif kind == "no_collector_lint":
            ok = not has_collector_lint
        elif kind == "lint_getparam":
            ok = has_getparam_lint
        elif kind == "no_getparam_lint":
            ok = not has_getparam_lint
        else:
            ok = False

        all_ok = all_ok and ok
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        print(f"        blocked={blocked}  new_lint={has_new_lint}  collector_lint={has_collector_lint}  getparam_lint={has_getparam_lint}")
        first = text.strip().splitlines()[0] if text.strip() else "(empty)"
        print(f"        reply[0]: {first[:110]}")

    print("=" * 78)
    print("OVERALL:", "ALL PASS" if all_ok else "SOME FAILED")
    proc.kill()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
