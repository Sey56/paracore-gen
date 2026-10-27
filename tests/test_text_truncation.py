"""Text output truncation keeps BOTH ends.

⚠ Why this exists: the second pre-release review found that a script's final `Println` could
   disappear — text output was cut at the first 20 lines, and a takeoff snippet prints its
   result LAST, so truncation hid exactly the value that was asked for. Tables already kept a
   tail (`TABLE_TAIL_ROWS`); text did not. These pin the head+tail contract.

⚠ Updated 2026-10-27 (review round 6): the text budget was raised from 20 lines (12 head +
   8 tail) to 40 lines (24 head + 16 tail). The reviewer's complaint was that "a script that
   does many transactions loses the middle lines" — the old 12+8 window hid 20 lines of a
   40-line transaction log; the new 24+16 window shows all 40, and only starts eliding at 41+.
   The tests below use an 80-line payload so the middle is genuinely hidden (80 − 24 − 16 = 40).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, r"C:\Users\seyou\Paracore\paracore\mcp")

from mcp_core.summarizer import (
    summarize, MAX_TEXT_LINES, MAX_TEXT_HEAD, MAX_TEXT_TAIL, SHOW_ALL_TEXT_THRESHOLD,
)


def text_payload(n):
    """`n` numbered lines — no keyword that would divert the short-output path."""
    return {"output": "\n".join(f"row {i:02d}" for i in range(1, n + 1))}


def has(out, needle):
    return needle in out


class TestTextTruncation:
    # ─── constants ───────────────────────────────────────────────────────
    def test_the_window_is_twenty_four_and_sixteen(self):
        assert MAX_TEXT_LINES == 40
        assert MAX_TEXT_HEAD == 24
        assert MAX_TEXT_TAIL == 16

    # ─── at the threshold (40 lines): nothing hidden ─────────────────────
    def test_at_threshold_the_last_line_survives(self):
        """40 lines = SHOW_ALL_TEXT_THRESHOLD, so nothing is elided."""
        out = summarize(text_payload(40))
        assert has(out, "row 40"), out
        assert not has(out, "not shown"), out

    def test_at_threshold_the_first_line_survives(self):
        out = summarize(text_payload(40))
        assert has(out, "row 01"), out

    def test_at_threshold_the_total_is_reported(self):
        """At the threshold the short-output path fires: '(40 lines)', not '— 40 lines total'."""
        out = summarize(text_payload(40))
        assert has(out, "(40 lines)"), out

    # ─── above the threshold (80 lines): head + tail, middle elided ──────
    def test_above_threshold_the_last_line_survives(self):
        """The whole point: the final line is the result, and it must be visible."""
        out = summarize(text_payload(80))
        assert has(out, "row 80"), out
        assert has(out, "row 65"), out          # first line of the 16-line tail (80-16+1)

    def test_above_threshold_the_first_line_survives(self):
        out = summarize(text_payload(80))
        assert has(out, "row 01"), out
        assert has(out, "row 24"), out          # last line of the 24-line head

    def test_above_threshold_the_middle_is_elided(self):
        out = summarize(text_payload(80))
        assert not has(out, "row 25"), out      # first hidden row
        assert not has(out, "row 64"), out      # last hidden row

    def test_above_threshold_it_says_how_many_lines_were_hidden(self):
        out = summarize(text_payload(80))
        # 80 - 24 - 16 = 40 hidden
        assert has(out, "40 line(s) not shown"), out

    def test_above_threshold_the_total_is_reported(self):
        out = summarize(text_payload(80))
        assert has(out, "80 lines total"), out

    # ─── short output ───────────────────────────────────────────────────
    def test_short_output_is_shown_whole(self):
        n = SHOW_ALL_TEXT_THRESHOLD
        out = summarize(text_payload(n))
        for i in range(1, n + 1):
            assert has(out, f"row {i:02d}"), f"row {i:02d} missing from {out!r}"
        assert not has(out, "not shown"), out
