#!/usr/bin/env python3
"""Probe: does the exe an agent will actually run BAN the pick — and carry no pick tool?

Why this exists (2026-10-28, operator ruling)
---------------------------------------------
The operator asked the right question: "Pick() is when the agent wants me to select
something in Revit — but how do I know it wants me to do that without any signal?"

Measured on his own screen: a bare `Pick()` showed him NOTHING. Revit's status bar carried
the add-in's generic "Executing dynamic query … Running …", which appears for every call,
so a pick was indistinguishable from a wall count. The status prompt itself only shows while
the pointer is already over Revit, and repaints on mouse movement — so an operator reading
the chat never sees it. His verdict: "it is not useful at all."

His ruling was therefore not "warn the agent" but "remove it": *"it was made for the human.
so let you make them not use it."* See `RETIRED.md` R11 / N4 in the `paracore` repo.

⚠ WHAT CHANGED FROM THE FIRST VERSION OF THIS PROBE. It used to assert a `PICKING` block in
  `paracore-gen`'s own `GEN_INTRO` — a per-domain warning. That block was deleted when the ban
  moved into `COMMON_RULES` in the shared core, so it now applies to EVERY domain and cannot
  drift between them. This probe asserts the shared text instead, and it is runnable against
  any of the five exes.

⚠ WHY IT ASKS THE EXE AND NOT THE SOURCE. `COMMON_RULES` is bundled INSIDE the PyInstaller
  exe and delivered as `instructions` in the handshake. A source edit proves nothing about
  the shipped artifact — and the exes are `--onefile`, so a stale copy is silent.

⚠ THE SECOND HALF IS TWO-SIDED. Telling an agent "never pick" while still handing it a
  `pick_object` tool would be a contradiction the agent has to resolve. Both halves must hold.

Usage:
    <python> spikes/probe_pick_protocol.py [path\\to\\<server>.exe]
Default path is dist\\paracore-gen.exe (check BEFORE installing). Any of the five works.
"""
import json
import subprocess
import sys
import threading
import time

EXE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\seyou\Paracore\paracore-gen\dist\paracore-gen.exe"

# Phrases from the COMMON_RULES ban block. Each one is load-bearing:
#   the first is the rule, the rest are the reason and the four alternatives it names.
COMMON_RULES_BAN = [
    "AND NEVER ASK THE USER TO CLICK FOR YOU",   # the rule itself, with its date
    "exists for a HUMAN writing a script",       # who it is for — not a blanket "broken"
    "holds Revit's UI thread until the user clicks",  # why the agent cannot warn in time
    "not useful at all",                         # the operator's measured verdict, quoted
    "THE USER SELECTS FIRST",                    # alternative 1
    "ASK BY NAME OR PARAMETER",                  # alternative 2
    "ASK THEM TO READ OUT AN ID",                # alternative 3
    "ASK A QUESTION",                            # alternative 4
    "do not reach for a pick",                   # the closing instruction
]

# ⚠⚠ FORGE DOES NOT USE COMMON_RULES. It builds its own `FastMCP` with a hand-written
#   `instructions=` literal (`forge_server.py`, "HARD RULES") AND composes a longer prompt from
#   `forge_core/prompts/*.md` served as the `forge://system-prompt` RESOURCE. The ban had to be
#   written in BOTH: the resource is the full ruleset, but a resource is only read if the client
#   asks for it — and this probe asserts the channel that is guaranteed to arrive.
#
#   ⚠ These phrases must stay on ONE LINE of the literal. The `instructions=` string is
#     triple-quoted with wrapping, so a phrase that spans a line break will never match.
FORGE_BAN = [
    "NEVER write `Pick()` into a tool",          # the rule
    "It makes the operator click",               # what it does to them
    "its only cue is Revit's status bar",        # why the agent cannot warn in time
    "visible only while the pointer is already",  # why the operator sees nothing
    "the run looks frozen",                      # what it feels like
    "plus a parameter filter",                   # alternative 2
    "belongs in a tool a HUMAN drives from the gallery",  # where it IS allowed
    "R11/N4",                                    # the tombstone, so it cannot drift back
]

REQUIRED_BY_SERVER = {"paracore-forge": FORGE_BAN}
DEFAULT_BAN = COMMON_RULES_BAN

# ⚠ `pick_object` must be absent from EVERY domain now, not just this one.
FORBIDDEN_TOOL = "pick_object"

# ⚠⚠ THE BAN IS ONLY MEANINGFUL WHERE THE AGENT CAN EXECUTE CODE. A server that exposes no
#   code-execution tool cannot call `Pick()` no matter what its prompt says, so demanding the
#   text there would be cargo-culting — and prompt bytes are not free.
#   Measured 2026-10-28 against the five built exes: gen (10 tools), family (10) and model (15)
#   carry the ban via `COMMON_RULES`; forge (17) composes its own prompt from
#   `forge_core/prompts/script-rules.md` and needed the row added there; takeoff (53) exposes
#   only domain tools — `get_levels`, `get_door_schedule`, `export_view` … — and NO way to run
#   code, so it is exempt by construction.
#
#   A server NOT listed here is treated as ABLE to execute, i.e. the ban is REQUIRED. That is
#   deliberate: fail closed. A new server must come here and say why it is exempt.
CANNOT_EXECUTE = {"paracore-takeoff"}

# What proves a server can run agent-authored code. If any is present the ban is required.
EXECUTOR_TOOLS = ("_execute_dynamic_query", "run_tool", "preview_tool", "dry_run")


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
                           "clientInfo": {"name": "pick-probe", "version": "2.0"}}})
    init = wait_for(msgs, 1, timeout=180.0)
    if init is None:
        print("FATAL: no initialize response")
        print("stderr tail:", "".join(logs[-20:]))
        proc.kill()
        return 2
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    instructions = (init.get("result", {}) or {}).get("instructions") or ""
    print(f"instructions: {len(instructions)} chars")

    send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    resp = wait_for(msgs, 2)
    names = [t.get("name") for t in (resp or {}).get("result", {}).get("tools", [])]
    present = FORBIDDEN_TOOL in names
    executors = [t for t in EXECUTOR_TOOLS if t in names]
    server = EXE.replace("/", "\\").rsplit("\\", 1)[-1].rsplit(".", 1)[0]

    # The ban is required unless this server is a declared non-executor. Unknown → required.
    exempt = server in CANNOT_EXECUTE and not executors
    print(f"tools: {len(names)} — {FORBIDDEN_TOOL} present: {present}")
    print(f"executors: {executors or 'none'}")
    print(f"ban required: {not exempt}"
          + (f"  (declared non-executor: {server})" if exempt else ""))

    failures = []
    if present:
        failures.append(f"{FORBIDDEN_TOOL} must be ABSENT from every domain (RETIRED.md R11)")

    if exempt:
        # Still assert the real question for a non-executor: it has no executor AND no pick.
        print("  -- exempt: this server cannot run agent code, so there is nothing to pick with")
    else:
        required = REQUIRED_BY_SERVER.get(server, DEFAULT_BAN)
        print(f"  ban set: {'forge' if server in REQUIRED_BY_SERVER else 'COMMON_RULES'} "
              f"({len(required)} phrases)")
        for needle in required:
            ok = needle in instructions
            print(f"  {'ok  ' if ok else 'MISS'} {needle}")
            if not ok:
                failures.append(needle)

    proc.kill()

    if failures:
        print(f"\nFAIL — {len(failures)} problem(s): {failures}")
        return 1
    if exempt:
        print(f"\nPASS — non-executor: no pick tool, no code execution, ban not applicable.")
        return 0
    print(f"\nPASS — the exe bans the pick in {len(required)} phrases, and has no pick tool.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
