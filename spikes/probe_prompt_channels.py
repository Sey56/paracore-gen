"""Which channels actually carry instruction text to the model, and what is lost?

WHY THIS EXISTS
    `mcp_core/prompt_assembler.build_prompt()` assembles ten `prompts/*.md` files into
    one 36 K string — and NOTHING CALLS IT. Only `globals.md` (as the `paracore://globals`
    resource) and `catalog.md` (as `build_extension_reference`'s fallback) are reachable.
    So the question "if 8 of 10 are inert, what IS the MCP using?" needs a measurement,
    not an assurance.

WHAT IT MEASURES
    1. The LIVE channels, with sizes:
         A  instructions=   (the initialize handshake)
         B  tool descriptions
         C  skill bodies    (read_skill, on demand)
         D  tool_helpers    (reactive: the error text a failed script gets back)
    2. Per dead file: what fraction of its distinctive vocabulary appears NOWHERE in
       A+B+C+D. A high miss rate means the file holds content that was never re-homed.

⚠ This is a VOCABULARY probe, not a semantic one: a shared word is not proof the rule
  survived, and a missing word is not proof it did not. Read the printed samples.

RUN  (from paracore-gen, dev mode — no Revit needed)
    mcp-build/.venv/Scripts/python.exe spikes/probe_prompt_channels.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_server  # noqa: E402  — binds sys.path to the sibling paracore/mcp core
from mcp_core import prompt_assembler as pa  # noqa: E402
from mcp_core import server as srv  # noqa: E402

CORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "paracore", "mcp", "mcp_core",
)

# A word counts as "distinctive" when it is long enough that a coincidental match is
# unlikely, and not a plumbing word that every C# or Revit sentence contains.
_STOP = {
    "element", "elements", "parameter", "parameters", "because", "without", "between",
    "another", "different", "instead", "revit", "paracore", "should", "before", "after",
    "always", "never", "calling", "returns", "output", "result", "results", "method",
    "methods", "category", "categories", "session", "everything", "something", "anything",
    "yourself", "themselves", "execution", "expression", "collection", "collections",
    "property", "properties", "instance", "instances", "correct", "incorrect",
}


def _words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z_.]{6,}", text):
        w = w.lower().strip("._")
        if len(w) >= 7 and w not in _STOP:
            out.add(w)
    return out


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def main() -> int:
    live_instr = srv.build_instructions(mcp_server.DOMAIN)

    tools = asyncio.run(mcp_server.mcp.list_tools())
    live_tools = "\n".join((t.description or "") + "\n" + (t.name or "") for t in tools)

    skills_dir = os.path.join(CORE, "skills")
    live_skills = ""
    for name in sorted(os.listdir(skills_dir)):
        live_skills += _read(os.path.join(skills_dir, name, "SKILL.md"))

    live_helpers = _read(os.path.join(CORE, "tool_helpers.py"))

    channels = {
        "A instructions": live_instr,
        "B tool descs": live_tools,
        "C skill bodies": live_skills,
        "D tool_helpers": live_helpers,
    }
    corpus = "\n".join(channels.values())
    corpus_words = _words(corpus)

    print("=" * 78)
    print("1. THE LIVE CHANNELS — what the model can actually read")
    print("=" * 78)
    for label, text in channels.items():
        print(f"  {label:<16} {len(text):>7,} chars")
    print(f"  {'TOTAL':<16} {sum(len(t) for t in channels.values()):>7,} chars")
    print(f"\n  (for scale) build_prompt() — the INERT channel: {len(pa.build_prompt(mcp_server.DOMAIN)):,} chars")

    print()
    print("=" * 78)
    print("2. PER PROMPT FILE — is its vocabulary present anywhere live?")
    print("=" * 78)
    print(f"  {'file':<26}{'words':>6}{'lost':>6}  reachable via")
    print("  " + "-" * 74)

    prompts_dir = os.path.join(CORE, "prompts")
    reach = {
        "globals.md": "get_globals() -> paracore://globals",
        "catalog.md": "build_extension_reference() fallback",
    }
    detail: dict[str, list[str]] = {}
    for fname in sorted(os.listdir(prompts_dir)):
        if not fname.endswith(".md"):
            continue
        text = _read(os.path.join(prompts_dir, fname))
        words = _words(text)
        lost = sorted(w for w in words if w not in corpus_words)
        detail[fname] = lost
        via = reach.get(fname, "NOTHING — dead file")
        print(f"  {fname:<26}{len(words):>6}{len(lost):>6}  {via}")

    print()
    print("=" * 78)
    print("3. WHAT THE DEAD FILES SAY THAT IS NOWHERE ELSE (sample vocabulary)")
    print("=" * 78)
    for fname, lost in detail.items():
        if fname in reach:
            continue
        if not lost:
            print(f"  {fname:<26} all vocabulary present live")
            continue
        sample = ", ".join(lost[:10])
        print(f"  {fname:<26} {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
