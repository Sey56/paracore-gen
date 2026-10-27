"""Read-only scan: is a Revit modal dialog open right now?

Uses the watcher's OWN detection code, and NEVER clicks. Run:
    mcp-build/.venv/Scripts/python.exe spikes/probe_dialogs.py [--close]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

# the SHARED core lives in the sibling `paracore/mcp` — same walk as mcp_server.py
_dir, _core = HERE, None
for _ in range(6):
    if os.path.isfile(os.path.join(_dir, "paracore", "mcp", "mcp_core", "__init__.py")):
        _core = os.path.join(_dir, "paracore", "mcp")
        break
    _up = os.path.dirname(_dir)
    if _up == _dir:
        break
    _dir = _up
if _core is None:
    raise SystemExit("shared MCP core not found")
sys.path.insert(0, _core)

from mcp_core import dialog_watcher as dw  # noqa: E402

revit = dw.find_revit()
print("revit hwnd:", revit)
if revit is None:
    print("Revit window not found.")
    sys.exit(0)

dialogs = dw.scan_dialogs(revit)
print("dialogs found:", len(dialogs))
for d in dialogs:
    print("---")
    for k, v in d.items():
        print(f"  {k}: {v!r}")
    print("  human_only:", dw.is_human_only(d))
    print("  call_in_flight (this process):", dw.call_in_flight())

if "--close" in sys.argv and dialogs:
    for d in dialogs:
        if dw.is_human_only(d):
            print("REFUSED (human-only):", d["title"])
            continue
        print("handling hwnd", d["hwnd"])
        dw._handle(d)
