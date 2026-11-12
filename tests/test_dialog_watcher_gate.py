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
    for _ in range(8):
        if os.path.isfile(os.path.join(_dir, "paracore-mcp-core", "mcp_core", "__init__.py")):
            _core = os.path.join(_dir, "paracore-mcp-core")
            break
        _up = os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(f"shared MCP core not found above {_here}")
    # TWO roots: `mcp_core` is in `paracore-mcp-core`; `grpc_client` stayed at `paracore/mcp`.
    _core = os.environ.get("PARACORE_MCP_CORE") or _core
    _wire = os.environ.get("PARACORE_WIRE_DIR") or os.path.join(
        os.path.dirname(_core), "paracore", "mcp"
    )
    if os.path.isdir(_wire) and _wire not in sys.path:
        sys.path.insert(0, _wire)
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


class TestExecuteScriptOpensTheGate:
    """THE 2026-11-11 HALF — Forge runs gallery tools over ExecuteScript, not ExecuteRepl.

    `execute_repl` was gated from the start, so gen/model/family worked. Forge's
    `run_tool`, `dry_run`, `preview_tool` and `export_view` all go through
    `execute_script`, which called the stub DIRECTLY. The resident watcher thread
    was up, the overlap warning was on screen, and every scan hit
    `if not call_in_flight(): continue` and logged NOTHING. DialogWatcher.txt
    contained only "watcher thread up" lines; the preview timed out with the
    dialog still up. Both halves (gate + watcher) must be asserted, because a
    missing gate is completely silent.
    """

    @staticmethod
    def _run(monkeypatch, *, hide_watcher=False):
        import grpc_client

        seen = {}

        class FakeStub:
            def ExecuteScript(self, request, timeout=None):  # noqa: N802 (gRPC name)
                seen["in_flight"] = dw.call_in_flight()
                return SimpleNamespace(
                    is_success=True, output="", error_message="",
                    error_details=[], structured_output=[], internal_data="",
                    pipeline_diagnostics=[], user_rejected=False,
                    confirmation="", session_consent="",
                )

        @contextmanager
        def fake_stub():
            yield FakeStub()

        monkeypatch.setattr(grpc_client, "get_corescript_runner_stub", fake_stub)
        if hide_watcher:
            # The desktop rap-server / manual Gallery script path imports NO
            # watcher module at all. `dw` is still held by this test module, so
            # call_in_flight() remains readable.
            monkeypatch.delitem(sys.modules, "mcp_core.dialog_watcher", raising=False)
            monkeypatch.delitem(sys.modules, "forge_core.dialog_watcher", raising=False)

        # ⚠ An explicit timeout keeps `_deadline` from probing the consent gate:
        #   this test is about the IN-FLIGHT gate, not the deadline policy.
        out = grpc_client.execute_script('Println("x");', "{}",
                                         source="mcp_agent", timeout=30)
        return out, seen

    def test_the_grpc_call_runs_inside_the_gate(self, monkeypatch):
        out, seen = self._run(monkeypatch)
        assert out["is_success"] is True
        assert seen.get("in_flight") is True, (
            "ExecuteScript ran OUTSIDE revit_call() — Forge's dialog watcher would "
            "never be allowed to answer a warning blocking it, and Revit would hang "
            "until a human clicked (measured: 'Highlighted floors overlap.', 2026-11-11)"
        )
        assert dw.call_in_flight() is False, "the gate was left open"

    def test_a_process_without_a_watcher_opens_no_gate(self, monkeypatch):
        """MANUAL desktop paths must stay untouched: the human closes their own dialogs."""
        out, seen = self._run(monkeypatch, hide_watcher=True)
        assert out["is_success"] is True
        assert seen.get("in_flight") is False, (
            "a process with no resident watcher must still run the script, but must "
            "NOT open a gate that would let a watcher answer the operator's dialogs"
        )


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


class TestDialogNoteIsNeverLost:
    """MEASURED 2026-11-11 13:10 — two 'Insert conflicts with joined Wall.'
    dialogs were answered (DialogWatcher.txt 13:10:13 and 13:10:29) but only the
    FIRST message reached the agent. A BLOCKING dialog parks Revit until the click;
    a NON-BLOCKING warning lets the tool result drain the capture buffer while
    click() is still confirming the close, and the next call's destructive pre-drain
    then throws the late record away. Every occurrence after the first was lost.
    """

    @staticmethod
    def _dlg():
        return {"hwnd": 12345, "title": "Autodesk Revit 2025",
                "text": "Resolve First Error:",
                "message": "Insert conflicts with joined Wall.",
                "buttons": [(1, "&OK", True), (2, "&Cancel", True)]}

    def test_record_is_published_before_the_click_completes(self):
        import threading
        started, release = threading.Event(), threading.Event()
        orig_click, orig_log = dw.click, dw.log
        dw.pop_captured()

        def slow_click(hwnd):
            started.set()
            release.wait(2.0)
            return True, "PostMessage(BM_CLICK)"

        th = None
        try:
            dw.click = slow_click
            dw.log = lambda *a, **k: None
            th = threading.Thread(target=dw._handle, args=(self._dlg(),))
            th.start()
            assert started.wait(2.0), "click never started"
            assert dw.captured_count() == 1, (
                "the record must exist WHILE click() is still confirming the close. "
                "Publishing it afterwards makes a non-blocking warning's drain see an "
                "empty buffer — exactly how the second occurrence was lost.")
        finally:
            release.set()
            if th is not None:
                th.join(2.0)
            dw.click, dw.log = orig_click, orig_log
            dw.pop_captured()

    def test_single_flight_never_discards_a_late_record(self):
        from mcp_core import tools
        dw.pop_captured()
        dw._record({"title": "T", "message": "late warning", "action": "keep",
                    "reason": "", "buttons": ["&OK"], "pressed": "&OK",
                    "closed": True})
        with tools.single_flight("probe"):
            assert dw.captured_count() == 1, (
                "a destructive pre-drain throws away a non-blocking warning recorded "
                "just after the previous call's drain. Report it late, never drop it.")
        dw.pop_captured()

    def test_every_occurrence_reaches_the_agent(self):
        from mcp_core import tools
        orig_log = dw.log
        try:
            dw.pop_captured()
            dw.log = lambda *a, **k: None
            for _ in range(2):
                dw._record({"title": "Autodesk Revit 2025",
                            "message": "Insert conflicts with joined Wall.",
                            "action": "keep", "reason": "warning-style",
                            "buttons": ["&OK", "&Cancel"], "pressed": "&OK",
                            "closed": True})
            note = tools._dialog_note()
            assert note.count("Insert conflicts with joined Wall.") == 2, (
                "two dialog INSTANCES must produce two messages; handling one must "
                "never suppress the next")
            assert "REVIT SHOWED A DIALOG WHILE THIS CALL RAN" in note
        finally:
            dw.log = orig_log
            dw.pop_captured()
