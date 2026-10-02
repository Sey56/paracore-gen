"""Assert that every prompt the assembler reads at runtime is bundled in the exe.

WHY
    `prompt_assembler.py` loads `mcp_core/prompts/*.md` at RUNTIME from
    `_PROMPTS_DIR = <dir of prompt_assembler.py>/prompts`. If that directory is
    absent from the PyInstaller bundle, `_read()` raises FileNotFoundError and
    returns the string `"[Prompt file not found: X]"` — so `build_prompt()` emits a
    system prompt consisting entirely of placeholders. The build reports SUCCESS.

    The result: the agent receives no Paracore API reference whatsoever, and
    nothing anywhere raises. Source runs and `pip` runs are unaffected, so the bug
    is invisible except from the frozen exe. This script is the gate for that.

WHY NOT A RAW BYTE SEARCH
    The PyInstaller PKG is compressed, so a `grep` for text that IS bundled returns
    0 — identical to text that is genuinely absent. Verified 2026-10-02: `grep -c`
    on the installed exe returned 0 for `BarGraph(data)` while the string was
    present. Use PyInstaller's own archive reader.

USAGE
    python verify_bundled_prompts.py <exe> <prompt_source_dir>
"""

import os
import sys

from PyInstaller.archive.readers import CArchiveReader


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_bundled_prompts.py <exe> <prompts_dir>")
        return 2

    exe, src_dir = sys.argv[1], sys.argv[2]

    expected = sorted(f for f in os.listdir(src_dir) if f.endswith(".md"))
    if not expected:
        # An empty expectation cannot fail, so it must not pass.
        print(f"GATE FAILED: no .md files in {src_dir}")
        return 1

    reader = CArchiveReader(exe)
    toc = getattr(reader, "toc", None) or getattr(reader, "_toc")
    names = [str(n) for n in toc]
    if len(names) < 50:
        print(f"GATE FAILED: only {len(names)} TOC entries — reader mis-read the exe")
        return 1

    normalized = [n.replace("\\", "/") for n in names]
    bundled = {
        n.rsplit("/", 1)[-1]
        for n in normalized
        if "mcp_core/prompts/" in n and n.endswith(".md")
    }

    missing = [f for f in expected if f not in bundled]

    print(f"  prompts on disk      : {len(expected)}")
    print(f"  prompts in the exe   : {len(bundled)}")
    if missing:
        print(f"  MISSING ({len(missing)}): {', '.join(missing)}")
        print("  => the frozen exe would serve '[Prompt file not found: ...]'")
        return 1

    # Present is not enough — verify one file's CONTENT round-trips, so a
    # stale or truncated entry cannot pass on its filename alone.
    probe = "globals.md"
    entry = next((n for n in names if n.replace("\\", "/").endswith("mcp_core/prompts/" + probe)), None)
    if entry is None:
        print(f"  could not locate {probe} for a content check")
        return 1
    data = reader.extract(entry).decode("utf-8", errors="replace")
    on_disk = open(os.path.join(src_dir, probe), encoding="utf-8").read()
    if data != on_disk:
        print(f"  CONTENT MISMATCH in {probe}: "
              f"exe={len(data)}B disk={len(on_disk)}B (stale bundle)")
        return 1

    print(f"  content round-trip   : {probe} {len(data)}B matches source  OK")
    print("  prompt bundling VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
