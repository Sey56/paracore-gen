"""`read_extension_methods()` with no query must cut on a SECTION boundary, and say so.

⚠ Why this exists: the third pre-release review called the no-query catalogue "the complete
   ~17,000-char catalog" and got back a document sliced through the middle of section 4 — a
   half-rendered snippet that reads as corruption, not as truncation. A caller cannot tell a
   truncated read from a short one unless the text says which it is.

   The fix is `_head_sections`: cut at the last COMPLETE `## ` heading before the budget, and
   append a trailer naming the character count and the way to get the rest. These pin that.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, r"C:\Users\seyou\Paracore\paracore\mcp")

from mcp_core.tool_helpers import _head_sections, search_extension_methods

TRAILER_MARK = "This is the START of "


def doc(sections, body_lines=40, names=None):
    """A synthetic catalogue: `## <name>` headings, each with a fenced body.

    ⚠ `names` matters for the query tests. The search splits a query into WORDS and takes the
    first section header containing any of them, so `## Section 0 … ## Section 3` cannot be
    told apart by the query "Section 3" — "section" matches the first one. Distinct names are
    what make a targeted query test meaningful.
    """
    names = names or [f"Section {i}" for i in range(sections)]
    parts = ["# Paracore Extension Methods", ""]
    for i, name in enumerate(names[:sections]):
        parts.append(f"## {name}")
        parts.append("")
        parts.append("```csharp")
        for j in range(body_lines):
            parts.append(f"// line {i}.{j} padding padding padding padding padding")
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


class TestHeadSections:
    def test_a_document_under_budget_is_returned_whole(self):
        d = doc(1)
        out = _head_sections(d, budget=len(d) + 100)
        assert out == d, "a document that fits must not be touched"

    def test_it_never_cuts_mid_snippet(self):
        """The defect: a fence sliced in half. Every returned fence must be closed."""
        d = doc(20)
        out = _head_sections(d, budget=4000)
        assert out.count("```") % 2 == 0, (
            f"odd number of fences ({out.count('```')}) — the cut landed inside a snippet"
        )

    def test_it_cuts_on_a_heading_boundary(self):
        """The precise property: the cut offset is exactly where a `## ` heading begins."""
        d = doc(20)
        out = _head_sections(d, budget=4000)
        m = re.search(r"TRUNCATED at ([\d,]+) of", out)
        assert m, f"no cut offset in the trailer: {out[-200:]!r}"
        cut = int(m.group(1).replace(",", ""))
        assert d[cut:].startswith("\n## "), (
            f"cut at {cut} does not land on a heading; next 40 chars: {d[cut:cut + 40]!r}"
        )
        # ...and therefore the retained text ends at a complete fence.
        assert d[:cut].rstrip().endswith("```"), (
            f"retained text ends with {d[:cut].rstrip()[-40:]!r}, not the end of a fence"
        )

    def test_the_trailer_says_it_is_truncated(self):
        out = _head_sections(doc(20), budget=4000)
        assert TRAILER_MARK in out, out[-200:]
        assert "TRUNCATED at" in out, out[-200:]

    def test_the_trailer_reports_real_numbers(self):
        d = doc(20)
        out = _head_sections(d, budget=4000)
        assert f"of {len(d):,} characters" in out, (
            f"trailer must state the FULL length {len(d):,}; got {out[-200:]!r}"
        )

    def test_the_trailer_offers_the_query_form(self):
        """The reader must be told what to do next, not just that it stopped."""
        out = _head_sections(doc(20), budget=4000)
        assert "read_extension_methods with a query" in out, out[-300:]

    def test_a_document_with_no_headings_still_stops(self):
        """No `## ` to cut on: fall back to the budget rather than returning everything."""
        flat = "\n".join(f"// line {i}" for i in range(2000))
        out = _head_sections(flat, budget=1000)
        assert len(out) < len(flat), "unbudgeted document was returned whole"
        assert "TRUNCATED at" in out, out[-200:]


class TestNoQueryPathUsesIt:
    def test_the_no_query_branch_is_truncated(self):
        """`search_extension_methods("")` is what the tool calls with no query."""
        d = doc(20)
        out = search_extension_methods("", d)
        assert TRAILER_MARK in out, (
            "the no-query path returned the raw head instead of the section-cut version"
        )
        assert out.count("```") % 2 == 0, "no-query path cut mid-snippet"

    def test_a_query_still_returns_a_match(self):
        d = doc(5, names=["Alpha", "Bravo", "Charlie", "Delta", "Echo"])
        out = search_extension_methods("Charlie", d)
        assert "Charlie" in out, out[:300]
        assert "Alpha" not in out, "the query returned the wrong section"
        assert TRAILER_MARK not in out, "a targeted query must not be head-truncated"
