"""Release check: the FROZEN exe refuses a raw write and leaks no machine identity.

WHY THIS EXISTS
    Source tests prove the functions; only the packaged exe proves what a customer runs.
    Three claims, each measured over MCP stdio against the shipped binary:
      1. `_explore_revit_data` REFUSES a raw `new Transaction(...)` — before Revit is
         touched. The canary builds a delegate it never invokes, so if the guard ever
         fails this check the model is still unchanged.
      2. `ping` no longer prints the Revit install path (it contained the Windows login).
      3. `get_context` no longer prints the user name.

USAGE
    python spikes/probe_exe_release.py [path-to-paracore-gen.exe]
    Default: ../dist/paracore-gen.exe. Needs Revit running with a model open.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "dist", "paracore-gen.exe")

CANARY = ('Func<Transaction> make = () => new Transaction(Doc, "guard probe");')

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
_id = 0


def call(method, params=None):
    global _id
    _id += 1
    msg = {"jsonrpc": "2.0", "id": _id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if m.get("id") == _id:
            return m


def tool(name, args):
    r = call("tools/call", {"name": name, "arguments": args})
    if r is None:
        return "<no response>"
    if "error" in r:
        return f"<error: {r['error']}>"
    c = r["result"].get("content") or []
    return c[0].get("text", "") if c else ""


def main() -> int:
    call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                        "clientInfo": {"name": "probe", "version": "0"}})
    proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                 "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    fails = []

    text = tool("_explore_revit_data",
                {"csharp_code": CANARY, "justification": "read-only guard canary"})
    ok = "READ-ONLY BLOCK" in text
    print(f"1. explore refuses `new Transaction(...)`: {'PASS' if ok else 'FAIL'}")
    if ok:
        print("   " + next(l for l in text.splitlines() if l.startswith("1.")))
    else:
        fails.append("guard")

    p = tool("ping", {})
    leak = "AppData" in p or "C:\\Program Files\\Autodesk" in p
    print(f"2. ping has no install path: {'PASS' if not leak else 'FAIL'}")
    if leak:
        fails.append("ping")
    else:
        print("   " + p.splitlines()[0])

    g = tool("get_context", {})
    has_user = any(line.startswith("User:") for line in g.splitlines())
    print(f"3. get_context has no User line: {'PASS' if not has_user else 'FAIL'}")
    if has_user:
        fails.append("get_context")

    # ── 4/5. agent file policy, on the frozen exe ───────────────────────────
    # ⚠ The WRITE tool, not explore: the file policy is not a read-only rule.
    overwrite = tool("_execute_dynamic_query", {
        "csharp_code": 'File.WriteAllText(p, text);',
        "justification": "file policy canary"})
    blocked = "agent file policy" in overwrite
    print(f"4. write tool refuses File.WriteAllText: {'PASS' if blocked else 'FAIL'}")
    if not blocked:
        fails.append("file_policy")

    create = tool("_execute_dynamic_query", {
        "csharp_code": ('var b = Encoding.UTF8.GetBytes("x");\n'
                        "using (var fs = new FileStream(p, FileMode.CreateNew)) "
                        "fs.Write(b, 0, b.Length);"),
        "justification": "create-new canary"})
    allowed = "agent file policy" not in create
    print(f"5. write tool allows FileMode.CreateNew: {'PASS' if allowed else 'FAIL'}")
    if not allowed:
        fails.append("create_new_blocked")

    proc.terminate()
    print("\nRESULT:", "all passed" if not fails else f"FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
