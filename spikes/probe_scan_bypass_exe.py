#!/usr/bin/env python3
"""Criterion A24 against the FROZEN EXE — before it is installed.

⚠⚠ WHY THIS EXISTS SEPARATELY FROM probe_scan_bypass.py. That probe drives the tool
functions in-process, so it proves the SOURCE is right. A shipped MCP is a PyInstaller
bundle: editing `tool_helpers.py` changes nothing in the exe until it is rebuilt. So "the
fix is in the source" and "the fix is in the artifact" are two different claims, and only
the second one is a release claim.

The scan runs BEFORE any gRPC call, so a refusal needs no Revit at all. The positive
controls do touch Revit, which is why this probe still wants the engine up.

Usage:
    python probe_scan_bypass_exe.py [path-to-exe]      # default: dist/paracore-gen.exe
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DEFAULT_EXE = REPO / "dist" / "paracore-gen.exe"
EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE

if not EXE.is_file():
    print(f"FATAL: exe not found at {EXE}")
    sys.exit(2)

print(f"EXE UNDER TEST: {EXE}")
st = EXE.stat()
print(f"  size={st.st_size}  mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}")

proc = subprocess.Popen(
    [str(EXE)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, encoding="utf-8", bufsize=1,
)

responses = {}
lock = threading.Lock()


def reader():
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in msg:
            with lock:
                responses[msg["id"]] = msg


threading.Thread(target=reader, daemon=True).start()

_next = [0]


def send(method, params=None, notify=False):
    _next[0] += 1
    rid = _next[0]
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        msg["id"] = rid
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    if notify:
        return None
    deadline = time.time() + 120
    while time.time() < deadline:
        with lock:
            if rid in responses:
                return responses.pop(rid)
        time.sleep(0.05)
    return None


def call_tool(name, args):
    resp = send("tools/call", {"name": name, "arguments": args})
    if not resp:
        return "<<no response>>"
    result = resp.get("result") or {}
    parts = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts) if parts else json.dumps(result)[:400]


results = []


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else "   <- " + str(detail)[:220]))


def refused(text):
    low = text.lower()
    return any(m in low for m in ("refus", "not allowed", "blocked", "violation", "forbidden",
                                  "disallowed", "not permitted", "dangerous pattern", "read-only"))


send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "scan-bypass-exe", "version": "1"}})
send("notifications/initialized", {}, notify=True)

print("=" * 78)
print("FROZEN EXE — qualified constructors must be refused before any gRPC call")
print("=" * 78)
for label, code in (
        ("Thread", 'var x = new System.Threading.Thread(() => { }); Println("RAN");'),
        ("HttpClient", 'var x = new System.Net.Http.HttpClient(); Println("RAN");'),
        ("Socket", 'var x = new System.Net.Sockets.Socket(1, 1, 1); Println("RAN");'),
        ("Process", 'System.Diagnostics.Process.Start("cmd.exe"); Println("RAN");'),
        ("StreamWriter", 'var x = new System.IO.StreamWriter("Z:\\\\__no_such_dir__\\\\p.txt"); Println("RAN");'),
):
    out = call_tool("_execute_dynamic_query",
                    {"csharp_code": code, "justification": "probe: scan bypass in the frozen exe"})
    check(f"frozen exe refuses: new ...{label}(...)", refused(out) and "RAN" not in out, out)

print()
print("=" * 78)
print("FROZEN EXE — controls: the scan must not have become a blanket refusal")
print("=" * 78)
out = call_tool("_execute_dynamic_query", {
    "csharp_code": 'Println("ALIVE=" + GetElements("Walls").Count());',
    "justification": "probe: a read-only query still executes through the frozen exe",
})
check("a read-only query still executes", "ALIVE=" in out, out)

out = call_tool("_explore_revit_data", {
    "csharp_code": '// never do new Transaction(Doc) in a read-only snippet\n'
                   'Println("PROSE_OK=" + GetElements("Walls").Count());',
    "justification": "probe: a comment naming a write must not refuse a correct query",
})
check("a comment naming a write does not refuse a correct query",
      "PROSE_OK=" in out and not refused(out), out)

out = call_tool("_explore_revit_data", {
    "csharp_code": 'var tx = new Autodesk.Revit.DB.Transaction(Doc); Println("RAN");',
    "justification": "probe: a qualified raw transaction must be refused by the read-only guard",
})
check("frozen exe read-only guard refuses a qualified Transaction", refused(out) and "RAN" not in out, out)

print()
try:
    proc.stdin.close()
except Exception:                                               # noqa: BLE001
    pass
try:
    proc.wait(timeout=10)
except Exception:                                               # noqa: BLE001
    proc.kill()

fails = sum(1 for ok, _ in results if not ok)
print("=" * 78)
print("%d/%d passed, %d failure(s)" % (len(results) - fails, len(results), fails))
print("=" * 78)
sys.exit(0 if fails == 0 else 1)
