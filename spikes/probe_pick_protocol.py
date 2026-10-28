#!/usr/bin/env python3
"""Probe: does the exe an agent will actually run carry the PICKING protocol?

Why this exists (2026-10-28)
----------------------------
The operator asked the right question: "Pick() is when the agent wants me to select
something in Revit — but how do I know it wants me to do that without any signal?"

Measured on his own screen: a bare `Pick()` showed him NOTHING. Revit's status bar carried
the add-in's generic "Executing dynamic query … Running …", which appears for every call,
so a pick was indistinguishable from a wall count. He clicked only because he had asked for
the pick. The agent cannot speak while the call blocks — so the ONLY fix that can reach the
user in time is an instruction the agent obeys BEFORE it calls.

That instruction lives in `GEN_INTRO`, which is bundled INSIDE the exe as `instructions`.
A source edit therefore proves nothing about the shipped artifact — this asks the exe.

⚠ The tools/list half is a two-sided check: `pick_object` must still be ABSENT from this
domain. A protocol that tells the agent how to pick while also handing it a pick tool would
be describing a tool this server deliberately does not have.

Usage:
    <python> spikes/probe_pick_protocol.py [path\\to\\paracore-gen.exe]
Default path is dist\\paracore-gen.exe (check BEFORE installing).
"""
import json
import subprocess
import sys
import threading
import time

EXE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\seyou\Paracore\paracore-gen\dist\paracore-gen.exe"

REQUIRED = [
    "PICKING — THIS SERVER HAS NO",          # the block exists at all
    "SAY SO IN CHAT FIRST",                  # the obligation
    "holds Revit's UI thread",               # why it matters
    "click the short wall by the stair",     # the example that teaches the prompt argument
    "Esc cancels",                           # the escape hatch (⚠ not "press Esc to cancel" —
                                             #   that is the ENGINE's default status prompt, a
                                             #   different string in a different artifact)
    "OperationCanceledException",            # what a cancel raises, so the agent can catch it
    "Selection",                             # the better alternative, named
]


def send(proc, obj):
    proc.stdin.write((json.dumps(obj) + "\n").encode())
    proc.stdin.flush()


def reader(proc, msgs, logs):
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msgs.append(json.loads(line))
        except Exception:
            logs.append(line)
    for line in proc.stderr:
        logs.append(line.decode("utf-8", "replace"))


def wait_for(msgs, want_id, timeout=120.0):
    end = time.time() + timeout
    while time.time() < end:
        for m in list(msgs):
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
                           "clientInfo": {"name": "pick-probe", "version": "1.0"}}})
    init = wait_for(msgs, 1, timeout=180.0)
    if init is None:
        print("FATAL: no initialize response")
        print("stderr tail:", "".join(logs[-20:]))
        proc.kill()
        return 2
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    instructions = (init.get("result", {}) or {}).get("instructions") or ""
    print(f"instructions: {len(instructions)} chars")

    failures = []
    for needle in REQUIRED:
        ok = needle in instructions
        print(f"  {'ok  ' if ok else 'MISS'} {needle}")
        if not ok:
            failures.append(needle)

    send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    resp = wait_for(msgs, 2)
    names = [t.get("name") for t in (resp or {}).get("result", {}).get("tools", [])]
    print(f"tools: {len(names)} — pick_object present: {'pick_object' in names}")
    if "pick_object" in names:
        failures.append("pick_object must be ABSENT from this domain")

    proc.kill()

    if failures:
        print(f"\nFAIL — {len(failures)} problem(s): {failures}")
        return 1
    print("\nPASS — the exe carries the pick protocol, and still has no pick tool.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
