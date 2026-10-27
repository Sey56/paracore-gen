"""What does the model ACTUALLY receive from paracore-gen?

Answers one question: the 10 `prompts/*.md` files are mostly inert — so what is the MCP
sending instead, and did the switch LOSE anything?

    mcp-build/.venv/Scripts/python.exe spikes/probe_prompt_surface.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _harness  # noqa: E402

_harness.boot(start_watcher=False)

from mcp_core import prompt_assembler as pa          # noqa: E402
from mcp_core.server import build_instructions, COMMON_RULES  # noqa: E402
from mcp_core.domain import SHARED_PROMPTS_DIR, render_catalogue_markdown  # noqa: E402

DOMAIN = sys.modules["mcp_server"].DOMAIN


def headings(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("#")]


print("=" * 78)
print("1. THE LIVE CHANNEL — what the handshake sends (`instructions=`)")
print("=" * 78)
live = build_instructions(DOMAIN)
print(f"build_instructions() : {len(live):>7,} chars")
print(f"  COMMON_RULES       : {len(COMMON_RULES):>7,}")
print(f"  Domain.intro       : {len(DOMAIN.intro):>7,}")
print(f"  skill catalogue    : {len(render_catalogue_markdown(DOMAIN)):>7,}")
print("\nits headings:")
for h in headings(live):
    print("   ", h)

print()
print("=" * 78)
print("2. THE INERT CHANNEL — `build_prompt()` (the OLD system prompt)")
print("=" * 78)
old = pa.build_prompt(DOMAIN)
print(f"build_prompt()       : {len(old):>7,} chars   <- assembled, never called")

print()
print("=" * 78)
print("3. PER FILE — is its content reachable at all?")
print("=" * 78)
print(f"{'file':24s} {'chars':>6s}  {'reachable via'}")
REACHABLE = {
    "globals.md": "get_globals() -> paracore://globals resource",
    "catalog.md": "build_extension_reference() FALLBACK only",
}
for name in sorted(os.listdir(SHARED_PROMPTS_DIR)):
    if not name.endswith(".md"):
        continue
    path = os.path.join(SHARED_PROMPTS_DIR, name)
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    print(f"{name:24s} {len(body):>6,}  {REACHABLE.get(name, 'NOTHING — dead file')}")

print()
print("=" * 78)
print("4. WHAT THE OLD PROMPT SAID THAT THE LIVE ONE DOES NOT")
print("=" * 78)
print("(a heading from a dead section, and whether its topic appears in the live text)")
TOPICS = {
    "identity.md": ["Session Start"],
    "script-rules.md": ["top-level", "class"],
    "retrieval.md": ["GetElements", "WhereParam"],
    "linq-rules.md": ["LINQ"],
    "parameter-discovery.md": ["CombinedParams"],
    "critical-rules.md": ["FORBIDDEN", "doc"],
    "verification.md": ["GetWarnings", "verify"],
    "common-patterns.md": ["GroupByParam"],
}
live_low = live.lower()
for fname, needles in TOPICS.items():
    path = os.path.join(SHARED_PROMPTS_DIR, fname)
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    covered = [n for n in needles if n.lower() in live_low]
    missing = [n for n in needles if n.lower() not in live_low]
    flag = "covered" if not missing else f"⚠ MISSING {missing}"
    print(f"  {fname:24s} {flag}")

print()
print("=" * 78)
print("5. THE SAME QUESTION FOR THE REAL RULES — count of hard rules per side")
print("=" * 78)
for label, text in (("live", live), ("old", old)):
    n_must = len(re.findall(r"\bNEVER\b|\bALWAYS\b|\bMUST\b", text))
    print(f"  {label:5s}: {len(text):>7,} chars, {n_must:>3} NEVER/ALWAYS/MUST occurrences")
