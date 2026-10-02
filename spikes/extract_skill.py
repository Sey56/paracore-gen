"""Extract a bundled data file from a PyInstaller onefile exe.

Usage: python extract_skill.py <exe> <name-substring> <dest> [check-phrase ...]
Prints what it found and what it wrote, then reports HAS[<phrase>] for each phrase
given on the command line (or a family-authoring default set if none are given).
Used to prove what a built MCP exe will actually serve, without needing the MCP
server to be running.
"""
import sys

from PyInstaller.archive.readers import CArchiveReader

exe, needle, dest = sys.argv[1], sys.argv[2], sys.argv[3]

reader = CArchiveReader(exe)
toc = getattr(reader, "toc", None)
if toc is None:
    toc = getattr(reader, "_toc", None)
if toc is None:
    print("NO TOC ATTRIBUTE; attrs =", [a for a in dir(reader) if not a.startswith("__")])
    sys.exit(2)

names = [n for n in toc if needle in n]
print("toc entries:", len(toc))
print("matching %r: %d" % (needle, len(names)))
for n in names:
    print("   ", n)

if not names:
    sys.exit(3)

name = names[0]
data = reader.extract(name)
with open(dest, "wb") as fh:
    fh.write(data)
print("wrote %s (%d bytes)" % (dest, len(data)))

text = data.decode("utf-8", errors="replace")
# Check phrases come from argv[4:]; fall back to the family-authoring defaults.
checks = sys.argv[4:] or [
    "Three mechanisms work through this API",
    "Two mechanisms work through this API",
    "The references are not geometric references",
    "between REFERENCE PLANES",
    "Fallback",
    "Metric Generic Model.rft",
]
for c in checks:
    print("HAS[%s] = %s" % (c, c in text))
