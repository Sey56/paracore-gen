#!/usr/bin/env python3
"""The SECURITY SCAN — the ~40 refused capabilities, in BOTH layers.

WHY THIS EXISTS (2026-10-29). The README makes a load-bearing claim:

    "The scan is the protection." — network, processes/threads/registry/native code,
    and the WHOLE reflection family are refused outright, by ENTRY POINT, in two places:
    the MCP server scans every snippet, and the add-in scans it a second time "so a direct
    gRPC caller cannot skip the first check."

Only TWO of those patterns had ever been probed (`new Transaction`, `File.WriteAllText`).
A hole in this scan is a Sev-1: the code is the only thing standing between an agent and
the machine. This probe tests ~24 refused patterns in BOTH layers, plus the documented
ALLOWANCES (two-sided, or a scan that refuses everything would pass).

⚠⚠ EVERY "MUST BE BLOCKED" SNIPPET IS HARMLESS IF IT ACTUALLY RUNS.
   A failing check here means the snippet EXECUTED. So each one is written to be inert:
   objects are CONSTRUCTED but never used to send, read, connect or start anything;
   registry and AppDomain access is READ-ONLY; `Process.Start` names a program that does
   not exist. If the scan fails, the worst outcome is a harmless object allocation or a
   "file not found" exception — never a network call, a spawned process or a file write.

⚠ TWO LAYERS, tested separately:
   LAYER 1 (MCP)    — `mcp_core.tools.execute_dynamic_query`, the shipped entry point.
   LAYER 2 (add-in) — `grpc_client.execute_repl` called DIRECTLY, bypassing layer 1.
   If layer 1 blocks and layer 2 does not, a direct gRPC caller walks straight through,
   which is exactly the scenario the README says is covered.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(WORKSPACE, "paracore-gen", "spikes"))

import _harness  # noqa: E402

t = _harness.boot()
import grpc_client  # noqa: E402

results = []


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else "   <- " + str(detail)))


# ── the two call paths ───────────────────────────────────────────────────
def layer1(code):
    """The shipped MCP tool path."""
    try:
        return t.execute_dynamic_query(code, "security-scan")
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


def layer2(code):
    """The add-in path, reached DIRECTLY so layer 1 cannot mask it."""
    try:
        r = grpc_client.execute_repl(code, "security-scan-direct",
                                     source="mcp_agent", timeout=60)
        if isinstance(r, dict):
            return " ".join(str(r.get(k, "")) for k in ("output", "error", "message"))
        return str(r)
    except Exception as exc:                                    # noqa: BLE001
        return "RAISED %s: %s" % (type(exc).__name__, exc)


# A snippet is BLOCKED when the reply says so, or when it never reaches "RAN".
def blocked(out):
    low = out.lower()
    markers = ("refus", "not allowed", "blocked", "violation", "forbidden",
               "disallowed", "not permitted", "security")
    if any(m in low for m in markers):
        return True
    # If the snippet ran, our sentinel is present -> NOT blocked.
    return "RAN" not in out


# ── the refused capabilities ─────────────────────────────────────────────
# (label, snippet) — every snippet is inert if executed.
CASES = [
    # network
    ("HttpClient",
     'var c = new System.Net.Http.HttpClient(); Println("RAN");'),
    ("WebClient",
     'var c = new System.Net.WebClient(); Println("RAN");'),
    ("WebRequest",
     'var r = System.Net.WebRequest.Create("http://127.0.0.1/"); Println("RAN");'),
    ("TcpClient",
     'var c = new System.Net.Sockets.TcpClient(); Println("RAN");'),
    ("UdpClient",
     'var c = new System.Net.Sockets.UdpClient(); Println("RAN");'),
    ("Socket",
     'var s = new System.Net.Sockets.Socket(System.Net.Sockets.SocketType.Stream, System.Net.Sockets.ProtocolType.Tcp); Println("RAN");'),
    ("Dns",
     'var h = System.Net.Dns.GetHostName(); Println("RAN");'),
    ("SmtpClient",
     'var c = new System.Net.Mail.SmtpClient(); Println("RAN");'),
    ("System.Net namespace",
     'var t = typeof(System.Net.HttpStatusCode); Println("RAN");'),
    # processes / threads / registry / native
    ("Process.Start",
     'System.Diagnostics.Process.Start("__paracore_probe_no_such_program__"); Println("RAN");'),
    ("ProcessStartInfo",
     'var psi = new System.Diagnostics.ProcessStartInfo("__none__"); Println("RAN");'),
    ("new Thread",
     'var th = new System.Threading.Thread(() => { }); Println("RAN");'),
    ("Registry",
     'var k = Microsoft.Win32.Registry.CurrentUser.Name; Println("RAN");'),
    ("Marshal",
     'int n = System.Runtime.InteropServices.Marshal.SizeOf(typeof(int)); Println("RAN");'),
    ("InteropServices",
     'var t = typeof(System.Runtime.InteropServices.Marshal); Println("RAN");'),
    # reflection — the whole family
    ("AppDomain",
     'var a = System.AppDomain.CurrentDomain.FriendlyName; Println("RAN");'),
    ("GetAssemblies",
     'int n = System.AppDomain.CurrentDomain.GetAssemblies().Length; Println("RAN");'),
    ("Activator",
     'var o = System.Activator.CreateInstance(typeof(string)); Println("RAN");'),
    ("System.Reflection",
     'var t = typeof(System.Reflection.BindingFlags); Println("RAN");'),
    ("GetTypes",
     'var ts = typeof(string).Assembly.GetTypes(); Println("RAN");'),
    ("GetMethod",
     'var m = typeof(string).GetMethod("ToString"); Println("RAN");'),
    ("GetProperty",
     'var p = typeof(string).GetProperty("Length"); Println("RAN");'),
    ("MethodInfo",
     'System.Reflection.MethodInfo mi = null; Println("RAN");'),
    # filesystem write (the documented refusal)
    ("File.WriteAllText",
     'System.IO.File.WriteAllText(System.IO.Path.Combine(System.IO.Path.GetTempPath(), "__paracore_probe_never_written__.txt"), "x"); Println("RAN");'),
]

print("=" * 78)
print("LAYER 1 — the shipped MCP tool")
print("=" * 78)
l1_blocked = 0
for label, code in CASES:
    out = layer1(code)
    ok = blocked(out)
    if ok:
        l1_blocked += 1
    check(f"L1 blocks {label}", ok, out.strip()[:160])

print()
print("=" * 78)
print("LAYER 2 — the add-in, reached DIRECTLY (bypassing layer 1)")
print("=" * 78)
l2_blocked = 0
for label, code in CASES:
    out = layer2(code)
    ok = blocked(out)
    if ok:
        l2_blocked += 1
    check(f"L2 blocks {label}", ok, out.strip()[:160])

# ── the documented ALLOWANCES — a scan that refuses everything would pass above ──
print()
print("=" * 78)
print("ALLOWED — these MUST run (two-sided control)")
print("=" * 78)

ALLOWED = [
    ("a normal model query",
     'Println("RAN " + GetElements("Walls").Count());'),
    ("Cast<dynamic> on grouped rows (the documented exception)",
     'var g = GetElements("Walls").GroupByParam("Type", "Length", "m");\n'
     'Println("RAN " + g.Count());'),
    ("SetExecutionTimeout as the first statement",
     'SetExecutionTimeout(30); Println("RAN");'),
]
for label, code in ALLOWED:
    out = layer1(code)
    check(f"ALLOWED: {label}", "RAN" in out, out.strip()[:200])

print()
fails = sum(1 for ok, _ in results if not ok)
print("=" * 78)
print("L1 blocked %d/%d · L2 blocked %d/%d"
      % (l1_blocked, len(CASES), l2_blocked, len(CASES)))
print("%d/%d passed, %d failure(s)" % (len(results) - fails, len(results), fails))
print("=" * 78)
sys.exit(0 if fails == 0 else 1)
