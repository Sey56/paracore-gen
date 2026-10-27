"""Gate: the dialog watcher is STARTED, and the in-flight gate OPENS.

WHY THIS EXISTS
    On 2026-10-27 15:42 a probe created a wall, Revit raised "Highlighted walls overlap",
    and Revit stayed parked on that modal dialog until a human clicked OK. The watcher was
    fine — it was never RUNNING in that process, and `execute_repl` never opened the gate,
    because the probe had imported the tools without `mcp_core.dialog_watcher`.

    Both halves are silent failures. Nothing raises, nothing logs, and the only symptom is
    a frozen Revit — which arrives minutes later and looks like a Revit problem. So they
    are asserted here rather than trusted:

        1. `revit_call()` sets the flag, and CLEARS it even when the body throws.
        2. `execute_repl` performs the gRPC call INSIDE the gate — this is the half that
           depends on a `sys.modules` lookup, and a second copy of the module would own a
           different counter and open nothing.
        3. `mcp_server.py` still starts the watcher from `__main__`.
"""

import os
import re
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

# ── the SHARED MCP CORE (`paracore/mcp`) — put it on sys.path ────────────────
if not getattr(sys, "frozen", False):
    _here = os.path.dirname(os.path.abspath(__file__))
    _dir, _core = _here, None
    for _ in range(6):
        if os.path.isfile(os.path.join(_dir, "paracore", "mcp", "mcp_core", "__init__.py")):
            _core = os.path.join(_dir, "paracore", "mcp")
            break
        _up = os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(f"shared MCP core not found above {_here}")
    sys.path.insert(0, _core)

from mcp_core import dialog_watcher as dw  # noqa: E402

REPO = os.path.dirname(_here)


class TestRevitCallGate:
    def test_the_flag_is_set_inside_and_cleared_after(self):
        assert dw.call_in_flight() is False
        with dw.revit_call():
            assert dw.call_in_flight() is True
        assert dw.call_in_flight() is False

    def test_the_flag_is_cleared_even_when_the_body_raises(self):
        """⚠ A leaked counter would leave the watcher permanently armed — and it would then
        answer the OPERATOR's dialogs, which is the 2026-10-10 failure all over again."""
        with pytest.raises(RuntimeError):
            with dw.revit_call():
                raise RuntimeError("boom")
        assert dw.call_in_flight() is False

    def test_nesting_does_not_clear_early(self):
        with dw.revit_call():
            with dw.revit_call():
                assert dw.call_in_flight() is True
            assert dw.call_in_flight() is True, "the inner exit cleared the outer call"
        assert dw.call_in_flight() is False


class TestExecuteReplOpensTheGate:
    def test_the_grpc_call_runs_inside_the_gate(self, monkeypatch):
        import grpc_client

        seen = {}

        class FakeStub:
            def ExecuteRepl(self, request, timeout=None):  # noqa: N802 (gRPC name)
                seen["in_flight"] = dw.call_in_flight()
                return SimpleNamespace(
                    is_success=True, output="", error_message="",
                    structured_output=[], pipeline_diagnostics=[],
                    session_consent="", user_rejected=False, read_only_violation=False,
                )

        @contextmanager
        def fake_stub():
            yield FakeStub()

        monkeypatch.setattr(grpc_client, "get_corescript_runner_stub", fake_stub)
        out = grpc_client.execute_repl('Println("x");', "gate-test")

        assert out["is_success"] is True
        assert seen.get("in_flight") is True, (
            "the gRPC call ran OUTSIDE revit_call() — the watcher would never be allowed to "
            "answer a dialog blocking it, and Revit would hang until a human clicked"
        )
        assert dw.call_in_flight() is False, "the gate was left open"


class TestServerStartsTheWatcher:
    def test_mcp_server_starts_it_from_main(self):
        path = os.path.join(REPO, "mcp_server.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        main_at = src.find('if __name__ == "__main__":')
        assert main_at != -1, "mcp_server.py has no __main__ block"
        assert "start_dialog_watcher" in src[main_at:], (
            "mcp_server.py no longer starts the dialog watcher from __main__. A probe or a "
            "script that imports the tools gets no watcher, and a warning dialog then blocks "
            "Revit with nothing able to close it."
        )

    def test_the_watcher_really_starts_and_is_idempotent(self):
        assert dw.start_dialog_watcher() is True
        assert dw.start_dialog_watcher() is False, "a second start must be a no-op, not a second thread"
