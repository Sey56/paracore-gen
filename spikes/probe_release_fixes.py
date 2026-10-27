#!/usr/bin/env python3
"""
Release asserts for the 2026-10-27 fix round — proves the EDITS reached the exe.

Two channels, because the two kinds of edit travel differently:
  * `server.COMMON_RULES` is a .py string  -> compiled into the PYZ, so it can only be
    read by ASKING the exe (the `initialize` response's `instructions`). CArchiveReader
    cannot see it.
  * `prompts/globals.md` is a --add-data entry -> a `datas` blob, readable directly.

⚠ Assert BOTH WAYS. A one-sided check cannot tell "corrected" from "deleted":
    MUST_CONTAIN    a phrase that exists only in the NEW text
    MUST_NOT_CONTAIN a phrase that exists only in the OLD text

Usage:
    <venv-python> spikes/probe_release_fixes.py [path\\to\\paracore-gen.exe]
"""
import json
import subprocess
import sys
import time

EXE = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\seyou\Paracore\paracore-gen\dist\paracore-gen.exe"

# ── what must be TRUE of the shared instruction block ────────────────────────────
INSTR_MUST_CONTAIN = [
    "PARACORE DIALOG WATCHER",                    # the watcher is now explained
    "A DIALOG IS NOT YOURS TO CLOSE",
    "REVIT SHOWED A DIALOG WHILE THIS CALL RAN",  # the note it will see
    "these RUN, with an advisory note attached",  # FORBIDDEN/AVOID split
]
INSTR_MUST_NOT_CONTAIN = [
    "A plan view is unaffected",
]

# ── what must be TRUE of the bundled globals prompt ──────────────────────────────
GLOBALS_MUST_CONTAIN = ["UIDoc"]
GLOBALS_MUST_NOT_CONTAIN = ["Uidoc"]

failures, checks = [], 0


def check(name, cond, detail=""):
    global checks
    checks += 1
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("   " + detail) if not cond else ""))
    if not cond:
        failures.append(name)


def read_instructions(exe):
    """Spawn the exe, run initialize, return result.instructions."""
    proc = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    try:
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2024-11-05",
                          "capabilities": {},
                          "clientInfo": {"name": "release-probe", "version": "1"}}}
        proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
        proc.stdin.flush()

        deadline = time.time() + 60
        while time.time() < deadline:
            raw = proc.stdout.readline()
            if not raw:
                break
            try:
                msg = json.loads(raw.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 1:
                return (msg.get("result") or {}).get("instructions") or ""
        return ""
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def read_bundled_globals(exe):
    """Extract the bundled prompts/globals.md out of the exe's datas archive."""
    from PyInstaller.archive.readers import CArchiveReader
    reader = CArchiveReader(exe)
    toc = getattr(reader, "toc", None) or getattr(reader, "_toc")
    names = [n for n in toc if "globals.md" in n]
    print("  bundled globals.md entries: %s" % names)
    if not names:
        return ""
    return reader.extract(names[0]).decode("utf-8", errors="replace")


def main():
    print("exe: %s" % EXE)

    print("\n-- instructions (initialize) --")
    text = read_instructions(EXE)
    check("instructions received", bool(text), "empty — initialize returned nothing")
    if text:
        for phrase in INSTR_MUST_CONTAIN:
            check("HAS[%s]" % phrase[:48], phrase in text)
        for phrase in INSTR_MUST_NOT_CONTAIN:
            check("LACKS[%s]" % phrase[:48], phrase not in text)

        # the FORBIDDEN list must now LEAD with `doc`, not with the raw collector.
        # ⚠ Bound the window at AVOID: the AVOID block IMMEDIATELY follows and legitimately
        #   names FilteredElementCollector, so a fixed-width window bleeds into it and reports
        #   a correct product as broken.
        idx = text.find("these WILL fail:")
        if idx >= 0:
            end = text.find("AVOID", idx)
            window = text[idx:end if end > idx else idx + 200]
            check("FORBIDDEN leads with doc/ActiveDocument", "ActiveDocument" in window,
                  "window=%r" % window[:120])
            check("FORBIDDEN no longer names FilteredElementCollector",
                  "FilteredElementCollector" not in window)
        else:
            check("FORBIDDEN block present", False, "not found")

    print("\n-- bundled prompts/globals.md --")
    try:
        g = read_bundled_globals(EXE)
    except Exception as e:
        check("extract globals.md", False, "%s: %s" % (type(e).__name__, e))
        g = ""
    if g:
        for phrase in GLOBALS_MUST_CONTAIN:
            check("HAS[%s]" % phrase, phrase in g)
        for phrase in GLOBALS_MUST_NOT_CONTAIN:
            check("LACKS[%s]" % phrase, phrase not in g)

    print("\n%d checks, %d failed" % (checks, len(failures)))
    if failures:
        print("FAILED: %s" % ", ".join(failures))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
