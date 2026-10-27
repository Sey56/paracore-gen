"""Boot the paracore-gen tool surface THE WAY THE SERVER DOES.

⚠⚠ WHY THIS EXISTS (2026-10-27). A probe that merely does `import mcp_server` gets the
tool functions but NOT the dialog watcher, because `mcp_server.py` starts it under
`if __name__ == "__main__"`. And `grpc_client.execute_repl` opens the in-flight gate by
looking for `mcp_core.dialog_watcher` in `sys.modules` — a module such a probe never
imports — so the call also ran WITHOUT the gate.

    Result, measured: a probe created a wall, Revit raised the "Highlighted walls
    overlap" warning, and NOTHING could close it. The watcher threads alive in the
    paracore-*.exe processes had no call of their own in flight, and by design they do
    not answer a dialog that is not theirs (that is what stops them closing the
    operator's own windows). Revit sat parked on a modal loop until a human clicked OK.

    So a probe is not "the same thing with a print". Boot through here and the watcher
    is resident and the gate opens, exactly as in the shipped server.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

_tools = None
_watcher = None


def _add_shared_core():
    """Put the sibling `paracore/mcp` on sys.path — the same walk as mcp_server.py."""
    if os.path.isfile(os.path.join(REPO, "paracore", "mcp", "mcp_core", "__init__.py")):
        core = os.path.join(REPO, "paracore", "mcp")
    else:
        core, d = None, REPO
        for _ in range(6):
            if os.path.isfile(os.path.join(d, "paracore", "mcp", "mcp_core", "__init__.py")):
                core = os.path.join(d, "paracore", "mcp")
                break
            up = os.path.dirname(d)
            if up == d:
                break
            d = up
    if core is None:
        raise RuntimeError("shared MCP core (paracore/mcp/mcp_core) not found")
    if core not in sys.path:
        sys.path.insert(0, core)


def boot(start_watcher: bool = True):
    """Import the server, start the resident watcher, return `mcp_core.tools`.

    ⚠ Call this FIRST in any probe that can MODIFY the model. A read-only probe that
    cannot raise a dialog does not need the watcher, but there is no harm in it.
    """
    global _tools, _watcher
    if _tools is not None:
        return _tools

    _add_shared_core()
    if REPO not in sys.path:
        sys.path.insert(0, REPO)

    import mcp_server  # noqa: F401  — builds DOMAIN and registers the tools
    from mcp_core import tools as tools_mod

    if start_watcher:
        # ⚠ Importing this is ALSO what lets grpc_client find the in-flight gate: it
        #   resolves `mcp_core.dialog_watcher` out of sys.modules, never by re-import,
        #   so a second copy could never open the gate.
        from mcp_core import dialog_watcher as watcher_mod
        _watcher = watcher_mod
        started = watcher_mod.start_dialog_watcher()
        print(f"[harness] dialog watcher started={started} "
              f"(pid={os.getpid()}, log={watcher_mod._log_path()})")

    _tools = tools_mod
    return _tools


def watcher():
    """The watcher module, once `boot()` has imported it."""
    return _watcher


def dialogs_open():
    """How many Revit modal dialogs are open right now (read-only)."""
    w = _watcher
    if w is None:
        raise RuntimeError("boot() first")
    revit = w.find_revit()
    return [] if revit is None else w.scan_dialogs(revit)
