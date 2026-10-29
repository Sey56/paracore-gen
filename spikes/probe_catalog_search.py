#!/usr/bin/env python3
"""Probe: is `read_extension_methods(query=...)` output COHERENT?

Why this exists (release review, 2026-10-28)
--------------------------------------------
The reviewer's most visible finding: the query path returned SPLICED text. Measured on
`query="WhereParam"`, the output contained

    * a sentence cut mid-way — "Category matching is exactly as lenient as the"
    * an orphan ``` with no opening fence, and a ```csharp block never closed
    * a heading belonging to a DIFFERENT section printed above a fragment

The cause was not the document — it was Pass 3 of `search_extension_methods`, which took a
±2-line window around every match and stapled on "the nearest header", found by walking
back up to 30 lines. A window is not an extraction.

⚠ THIS IS A REGRESSION PROBE, NOT A STYLE CHECK. Each assertion below maps to something a
  reader would actually see and be misled by. It runs OFFLINE against the source doc, so it
  costs a second and can gate every commit — unlike the live probes, which need Revit.

Usage:
    <python> spikes/probe_catalog_search.py [path\\to\\EXTENSION_METHODS.md]
Default doc is the one bundled beside this repo; the core is imported from ../paracore/mcp.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent
DOC = Path(sys.argv[1]) if len(sys.argv) > 1 else GEN / "EXTENSION_METHODS.md"
CORE = GEN.parent / "paracore" / "mcp"

if not DOC.is_file():
    print(f"FATAL: catalogue not found at {DOC}")
    sys.exit(2)
if not (CORE / "mcp_core" / "tool_helpers.py").is_file():
    print(f"FATAL: shared core not found at {CORE}")
    sys.exit(2)

sys.path.insert(0, str(CORE))
from mcp_core.tool_helpers import search_extension_methods  # noqa: E402

doc = DOC.read_text(encoding="utf-8")
doc_lines = set(doc.split("\n"))

# Queries that exercise all three passes, plus the one the review broke.
QUERIES = ["WhereParam", "Pick", "Table", "Transact", "SetParam", "GetStr", "GroupByParam"]

results: list[tuple[bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((ok, f"{label}{('  — ' + detail) if detail and not ok else ''}"))


for q in QUERIES:
    out = search_extension_methods(q, doc)
    tag = f'[{q}]'

    check(f"{tag} returns something", bool(out.strip()), f"{len(out)} chars")

    # 1. Fences must pair. An odd count means a code block opened and never closed, which
    #    renders every following line as code for the reader.
    fences = out.count("```")
    check(f"{tag} code fences balanced", fences % 2 == 0, f"{fences} fences")

    # 2. No invented headings: every `## ` line emitted must exist verbatim in the source.
    #    The old code manufactured headings via `_find_nearest_header` and printed them as
    #    `### <header>` above a fragment — so the heading described text it did not govern.
    invented = [ln for ln in out.split("\n") if ln.startswith("## ") and ln not in doc_lines]
    check(f"{tag} no invented headings", not invented, f"{invented[:2]}")

    # 3. Every emitted section is either verbatim from the source or explicitly says it was
    #    cut for budget. Anything else is spliced text.
    for sec in out.split("\n## ")[1:]:
        if "continues past" in sec or "NOT shown" in sec:
            continue
        body = sec.rstrip()
        if body.endswith("whole."):        # the "not shown" trailer rides on the last section
            body = body[: body.rfind("\n\n… ")].rstrip()
        check(f"{tag} section verbatim: {sec.splitlines()[0][:44]}", body in doc,
              "not found verbatim in the source")

# 4. THE ORIGINAL DEFECT, named exactly. The sentence must complete.
out_wp = search_extension_methods("WhereParam", doc)
check("WhereParam: the truncated sentence now completes",
      'exactly as lenient as the\n`GetElements("Category")`' in out_wp
      or 'exactly as lenient as the `GetElements("Category")`' in out_wp,
      "still cut at 'exactly as lenient as the'")

# 5. The Table of Contents is navigation, not an answer. `query="Table"` matched
#    "## 📖 Table of Contents" and returned the contents page for the most-used method.
out_t = search_extension_methods("Table", doc)
check("Table: does not return the contents page",
      "Table of Contents" not in out_t.split("\n")[1],
      f"first heading was {out_t.split(chr(10))[1][:60]!r}")
check("Table: returns real content", ".Table()" in out_t, "no .Table() in the answer")

passed = sum(1 for ok, _ in results if ok)
failed = [(ok, msg) for ok, msg in results if not ok]

print(f"doc: {DOC.name}  ({len(doc):,} chars)")
print(f"queries: {len(QUERIES)}   checks: {len(results)}\n")
for ok, msg in failed:
    print(f"  FAIL  {msg}")
if failed:
    print(f"\n{len(failed)} of {len(results)} check(s) FAILED")
    sys.exit(1)
print(f"PASS — all {passed} checks. Query output is coherent: whole sections, paired fences, "
      "no invented headings.")
sys.exit(0)
