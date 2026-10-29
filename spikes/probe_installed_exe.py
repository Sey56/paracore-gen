#!/usr/bin/env python3
"""Probe: the INSTALLED paracore-gen.exe, spoken to over stdio exactly as a client does.

Why this exists (2026-10-29)
----------------------------
Every other live probe imports `mcp_core` from SOURCE, so it proves the source tree and
says nothing about the frozen exe a user actually runs. A PyInstaller build is a snapshot:
a `.py` edit is inert until rebuild + install + restart. This probe boots the INSTALLED
binary, performs the MCP handshake, and asserts on what comes back.

What it covers here:
  * the handshake and the tool list (a server that cannot list its tools is dead on arrival);
  * `ping` -> the engine is reachable;
  * the BULK advisory, TWO-SIDED: a single element obtained from `.Duplicate()` must stay
    silent, a collection must still warn. `.Duplicate()` is the branch added today —
    without it the detector printed BULK OPERATION for a delete of exactly one element.

It is non-destructive: the duplicated type is deleted in the same script, and the type
count is compared before and after.

Usage:
    <python> spikes/probe_installed_exe.py [path\\to\\paracore-gen.exe]
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

DEFAULT_EXE = Path.home() / "AppData" / "Roaming" / "paracore-data" / "mcp-servers" / "paracore-gen.exe"
EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE

if not EXE.is_file():
    print(f"FATAL: installed exe not found at {EXE}")
    sys.exit(2)

print(f"EXE UNDER TEST: {EXE}")
print(f"  size={EXE.stat().st_size}  mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(EXE.stat().st_mtime))}")

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

_next_id = [0]


def send(method, params=None, notify=False):
    _next_id[0] += 1
    rid = _next_id[0]
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        msg["id"] = rid
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    if notify:
        return None
    deadline = time.time() + 180
    while time.time() < deadline:
        with lock:
            if rid in responses:
                return responses.pop(rid)
        time.sleep(0.05)
    return None


def call_tool(name, args):
    r = send("tools/call", {"name": name, "arguments": args})
    if not r:
        return ""
    if "error" in r:
        return json.dumps(r["error"])
    out = []
    for item in r.get("result", {}).get("content", []):
        if item.get("type") == "text":
            out.append(item.get("text", ""))
    return "\n".join(out)


results = []


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"   <- {detail}"))


# ── handshake ─────────────────────────────────────────────────────────────
init = send("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "probe_installed_exe", "version": "0"},
})
check("handshake succeeds", init is not None and "result" in (init or {}), str(init)[:300])
if init and "result" in init:
    server_info = init["result"].get("serverInfo", {})
    print(f"  serverInfo: {server_info}")
send("notifications/initialized", {}, notify=True)

tools_resp = send("tools/list", {})
names = []
if tools_resp and "result" in tools_resp:
    names = sorted(t["name"] for t in tools_resp["result"].get("tools", []))
print(f"  tools ({len(names)}): {', '.join(names)}")
# ⚠ THE REAL NAMES CARRY A LEADING UNDERSCORE (`_execute_dynamic_query`) — that is the
# documented, shipped name (see paracore-gen/README.md), not a typo in this probe. The
# server's own docstrings still say `execute_dynamic_query` in two places, which is a docs
# inconsistency, not a tool the client can call.
for required in ("ping", "get_context", "_execute_dynamic_query", "_explore_revit_data",
                 "_read_extension_methods", "_search_schema", "export_view",
                 "get_globals", "list_skills", "read_skill"):
    check(f"tool '{required}' is registered", required in names, str(names))

# ── the engine is reachable ───────────────────────────────────────────────
ping = call_tool("ping", {})
check("ping reaches the engine", "connect" in ping.lower() or "ok" in ping.lower(), ping[:300])

# ── BULK advisory, two-sided, on the installed binary ─────────────────────
before = call_tool("_execute_dynamic_query", {
    "csharp_code": 'Println("WALLTYPES " + GetElements("WallTypes").Count());',
    "justification": "probe: count wall types before the duplicate round-trip",
})
print(f"  wall types before: {before.strip()[:120]}")

single = call_tool("_execute_dynamic_query", {
    "csharp_code": (
        # ⚠ `Element` has no Duplicate(); the cast is what makes the receiver a
        # WallType. Without it the script fails to COMPILE and the "no bulk warning"
        # assertion below would pass for the wrong reason (nothing ran at all).
        # ⚠⚠ WRAP IN Transact (2026-10-29). `Duplicate` and `Delete` are RAW Revit API
        #   calls — the engine's auto-transaction only covers Paracore methods. A bare
        #   `wt.Duplicate(...)` runs OUTSIDE any transaction: Revit applies part of it
        #   (the type IS created) and then throws, leaving the copy behind. The probe
        #   then reports "model changed" and blames the product, when the product's own
        #   doc says to wrap raw API writes in `Transact("…", () => …)`. Wrap them.
        'var wt = (WallType)new FilteredElementCollector(Doc).OfClass(typeof(WallType)).First();\n'
        'Transact("probe: duplicate + delete one type", () => {\n'
        '    var dup = wt.Duplicate("PC-PROBE-DUP");\n'
        '    dup.Delete();\n'
        '});\n'
        'Println("DUP_ROUNDTRIP_OK");'
    ),
    "justification": "probe: single-element duplicate + delete (must NOT report bulk)",
})
check("single-element .Duplicate()/.Delete() executes", "DUP_ROUNDTRIP_OK" in single, single[:500])
check("single-element write does NOT print BULK OPERATION",
      "BULK OPERATION" not in single, single[:500])

bulk = call_tool("_execute_dynamic_query", {
    "csharp_code": 'GetElements("Walls").WhereParam("Comments", "PC-NEVER-MATCHES").Delete();',
    "justification": "probe: collection delete over an empty filter (must warn, deletes nothing)",
})
check("collection write still prints BULK OPERATION", "BULK OPERATION" in bulk, bulk[:500])

after = call_tool("_execute_dynamic_query", {
    "csharp_code": 'Println("WALLTYPES " + GetElements("WallTypes").Count());',
    "justification": "probe: count wall types after the round-trip",
})
import re as _re
_m = lambda t: (_re.search(r"WALLTYPES (\d+)", t) or [None, None])[1]
check("the model is unchanged (wall-type count)", _m(before) is not None and _m(before) == _m(after),
      f"before={_m(before)} after={_m(after)}")

try:
    proc.stdin.close()
except Exception:
    pass
proc.terminate()

fails = sum(1 for ok, _ in results if not ok)
print(f"\n{len(results) - fails}/{len(results)} passed, {fails} failure(s)")
sys.exit(0 if fails == 0 else 1)
