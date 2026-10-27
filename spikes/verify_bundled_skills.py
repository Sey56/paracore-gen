"""Assert that all nine skills are bundled in the exe.

WHY
    `read_skill(name)` resolves `<bundle>/mcp_core/skills/<name>/SKILL.md` at RUNTIME.
    When the skills directory is absent from the PyInstaller bundle, `load_skill_text`
    returns None and `read_skill` answers:

        No skill named 'query-filter'. Available: query-filter, aggregate-group, ...

    — a POLITE, PLAUSIBLE-LOOKING list of the very skills it cannot open. Nothing
    raises, the build reports SUCCESS, and a source run is unaffected. This is the
    same failure shape `verify_bundled_prompts.py` exists for, one directory over, and
    it is what a pre-release reviewer described as "the skills are listed, but I
    couldn't open any of them" (2026-10-27).

WHY NOT A RAW BYTE SEARCH
    The PyInstaller PKG is compressed, so `grep` for text that IS bundled returns 0 —
    identical to text that is genuinely absent. Use PyInstaller's own archive reader.

USAGE
    python verify_bundled_skills.py <exe> <skills_dir>
"""

import os
import sys

from PyInstaller.archive.readers import CArchiveReader


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_bundled_skills.py <exe> <skills_dir>")
        return 2

    exe, src_dir = sys.argv[1], sys.argv[2]

    expected = sorted(
        d for d in os.listdir(src_dir)
        if os.path.isfile(os.path.join(src_dir, d, "SKILL.md"))
    )
    if not expected:
        # An empty expectation cannot fail, so it must not pass.
        print(f"GATE FAILED: no <skill>/SKILL.md under {src_dir}")
        return 1

    reader = CArchiveReader(exe)
    toc = getattr(reader, "toc", None) or getattr(reader, "_toc")
    names = [str(n) for n in toc]
    if len(names) < 50:
        print(f"GATE FAILED: only {len(names)} TOC entries — reader mis-read the exe")
        return 1

    normalized = [n.replace("\\", "/") for n in names]
    bundled = {
        n.split("mcp_core/skills/", 1)[1].split("/")[0]
        for n in normalized
        if "mcp_core/skills/" in n and n.endswith("SKILL.md")
    }

    missing = [s for s in expected if s not in bundled]

    print(f"  skills on disk      : {len(expected)}")
    print(f"  skills in the exe   : {len(bundled)}")
    if missing:
        print(f"  MISSING ({len(missing)}): {', '.join(missing)}")
        print("  => read_skill would answer 'No skill named ...' for these")
        return 1

    # Present is not enough — verify one file's CONTENT round-trips, so a stale or
    # truncated entry cannot pass on its filename alone.
    probe = "query-filter"
    entry = next(
        (n for n in names
         if n.replace("\\", "/").endswith(f"mcp_core/skills/{probe}/SKILL.md")),
        None,
    )
    if entry is None:
        print(f"  could not locate {probe}/SKILL.md for a content check")
        return 1
    data = reader.extract(entry)
    with open(os.path.join(src_dir, probe, "SKILL.md"), "rb") as f:
        on_disk = f.read()
    # ⚠⚠ BYTES, not text — a text-mode read collapses CRLF to LF and reports a false
    #   "stale bundle". See the same note in verify_bundled_prompts.py (measured
    #   2026-10-27: globals.md, 83 CRLF pairs, build failed on a correct bundle).
    if data != on_disk:
        print(f"  CONTENT MISMATCH in {probe}: "
              f"exe={len(data)}B disk={len(on_disk)}B (stale bundle)")
        return 1

    print(f"  content round-trip   : {probe}/SKILL.md {len(data)}B matches source  OK")
    print("  skill bundling VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
