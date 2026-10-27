"""Reproduce the 15:42 dialog — WITH the watcher resident — and prove it is handled.

The failure being reproduced: a probe created a wall, Revit raised

    "Highlighted walls overlap. One of them may be ignored when Revit finds room
     boundaries. Use Cut Geometry to embed one wall within the other."

and nothing closed it. Root cause: the probe imported `mcp_server` but never started
the watcher, and `execute_repl` therefore also ran WITHOUT the in-flight gate — the
watcher in the real server process had no call of its own to answer.

This probe boots through `_harness.boot()`, so the watcher IS resident and the gate IS
open, then provokes the SAME warning on purpose.

    mcp-build/.venv/Scripts/python.exe spikes/probe_watcher_repro.py
"""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _harness  # noqa: E402

t = _harness.boot()
w = _harness.watcher()

LOG = w._log_path()


def log_lines():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


before = log_lines()
print(f"[before] dialog log has {len(before)} lines")

# ── model state before ───────────────────────────────────────────────────────
print(t.explore_revit_data(
    'Println("walls=" + GetElements("Walls").Count()); '
    'Println("probe walls=" + GetElements("Walls").WhereParam("Comments", "E2E_PROBE").Count());',
    "repro: baseline").strip())

# ── provoke the warning, in a thread so the script cannot hang silently ──────
CODE = (
    'Transact("repro overlap", () => { var lvl = GetElements<Level>().First(); '
    'var w = Wall.Create(Doc, Line.CreateBound(new XYZ(0,0,0), new XYZ(3.InputUnit("m"),0,0)), '
    'lvl.Id, false); w.SetVal("Comments", "E2E_PROBE"); }); Println("CREATE RETURNED");'
)

box = {}


def run():
    try:
        box["out"] = t.execute_dynamic_query(CODE, "repro: provoke the overlap warning")
    except Exception as exc:  # noqa: BLE001
        box["out"] = f"RAISED {type(exc).__name__}: {exc}"


th = threading.Thread(target=run, daemon=True)
th.start()
th.join(timeout=90)

if th.is_alive():
    print("\n!!! HUNG — the call never returned. Dialogs open now:")
    for d in _harness.dialogs_open():
        print("   ", d.get("message", "")[:100], d.get("buttons"))
    print("    Close them with: spikes/probe_dialogs.py --close")
    sys.exit(2)

print("\n[call returned]")
print(box.get("out", "")[:600])

after = log_lines()
new = after[len(before):]
print(f"\n[after] {len(new)} new dialog-log line(s):")
for line in new:
    print("   ", line)

closed = any("clicked" in l for l in new)
seen = any("DIALOG" in l for l in new)
print("\nRESULT:")
print("  watcher SAW the dialog :", seen)
print("  watcher CLOSED it      :", closed)

# ── clean up ─────────────────────────────────────────────────────────────────
print("\n[cleanup]")
print(t.execute_dynamic_query(
    'GetElements("Walls").WhereParam("Comments", "E2E_PROBE").Delete(); '
    'Println("walls=" + GetElements("Walls").Count());', "repro: cleanup").strip()[-300:])

sys.exit(0 if (seen and closed) else 1)
