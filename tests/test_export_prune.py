"""The export-view prune: our own stale images go, everything else stays.

⚠ Why this exists: the pre-release review found "a temp file left in Windows Temp".
   `export_view` writes a fresh PNG into %TEMP%\\paracore_views on every call and nothing
   removed them, so the folder grew without limit. These tests pin the narrow predicate —
   OUR directory, OUR `view_` prefix, an image extension, past the cutoff.

⚠ The tests point `tools._VIEW_EXPORT_DIR` at a fixed scratch folder and clear only the
   files they planted, by name. No directory tree is ever removed.
"""
import contextlib
import os
import sys
import tempfile
import time

sys.path.insert(0, r"C:\Users\seyou\Paracore\paracore\mcp")

from mcp_core import tools

SCRATCH = os.path.join(tempfile.gettempdir(), "paracore_prune_test")
_PLANTED = ("view_old.png", "view_fresh.png", "other_old.png",
            "view_old.txt", "view_olddir")


def _clear_planted():
    """Remove only the files this module creates, each by explicit name."""
    for name in _PLANTED:
        path = os.path.join(SCRATCH, name)
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            os.rmdir(path)          # only ever empty: the tests plant no file inside


def _plant(name, age_seconds, is_dir=False):
    path = os.path.join(SCRATCH, name)
    if is_dir:
        os.makedirs(path, exist_ok=True)
        return path
    with open(path, "w") as fh:
        fh.write("x")
    os.utime(path, (age_seconds, age_seconds))
    return path


@contextlib.contextmanager
def scratch_dir():
    """A fixture folder, with the module's constant redirected and restored."""
    saved = tools._VIEW_EXPORT_DIR
    os.makedirs(SCRATCH, exist_ok=True)
    _clear_planted()
    tools._VIEW_EXPORT_DIR = SCRATCH
    try:
        yield SCRATCH
    finally:
        tools._VIEW_EXPORT_DIR = saved
        _clear_planted()


OLD = time.time() - 30 * 86400
NOW = time.time()


class TestExportPrune:
    def test_removes_an_image_older_than_the_cutoff(self):
        with scratch_dir():
            _plant("view_old.png", OLD)
            assert tools._prune_old_exports() == 1
            assert not os.path.exists(os.path.join(SCRATCH, "view_old.png"))

    def test_keeps_a_recent_image(self):
        with scratch_dir():
            _plant("view_fresh.png", NOW)
            assert tools._prune_old_exports() == 0
            assert os.path.exists(os.path.join(SCRATCH, "view_fresh.png"))

    def test_keeps_a_file_this_tool_did_not_write(self):
        with scratch_dir():
            _plant("other_old.png", OLD)
            assert tools._prune_old_exports() == 0
            assert os.path.exists(os.path.join(SCRATCH, "other_old.png"))

    def test_keeps_a_non_image_with_our_prefix(self):
        with scratch_dir():
            _plant("view_old.txt", OLD)
            assert tools._prune_old_exports() == 0
            assert os.path.exists(os.path.join(SCRATCH, "view_old.txt"))

    def test_keeps_a_directory_even_with_our_prefix(self):
        with scratch_dir():
            _plant("view_olddir", OLD, is_dir=True)
            assert tools._prune_old_exports() == 0
            assert os.path.isdir(os.path.join(SCRATCH, "view_olddir"))

    def test_a_second_sweep_is_a_no_op(self):
        with scratch_dir():
            _plant("view_old.png", OLD)
            tools._prune_old_exports()
            assert tools._prune_old_exports() == 0

    def test_a_missing_directory_does_not_raise(self):
        saved = tools._VIEW_EXPORT_DIR
        tools._VIEW_EXPORT_DIR = os.path.join(SCRATCH, "no_such_dir_here")
        try:
            assert tools._prune_old_exports() == 0
        finally:
            tools._VIEW_EXPORT_DIR = saved

    def test_the_window_is_a_week(self):
        assert tools._VIEW_EXPORT_KEEP_DAYS == 7
