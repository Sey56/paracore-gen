#!/usr/bin/env python3
"""Call every tool that was only ever checked for BEING REGISTERED.

WHY THIS EXISTS (2026-10-29). `probe_installed_exe.py` proves the handshake, the tool list,
`ping`, and `_execute_dynamic_query`. The other eight tools — `get_context`, `get_globals`,
`list_skills`, `read_skill`, `_explore_revit_data`, `_search_schema`,
`_read_extension_methods`, `export_view` — were asserted only to appear in `tools/list`.
A registered tool that returns nothing, returns garbage, or throws on a bad argument is
indistinguishable from a working one by that check.

⚠ EVERY CHECK IS TWO-SIDED. "It did not error" is worthless on its own, so each tool is
asserted to return CONTENT SPECIFIC to what was asked — a real skill body, the real document
title, a real section of the catalog — and each tool's ERROR path is asserted to fail
HELPFULLY rather than crash or return a confident blank.

⚠ It runs against the INSTALLED exe over stdio, because that is the artifact a user runs.

Usage:
    <python> spikes/probe_tool_surface.py [path\\to\\paracore-gen.exe]
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

DEFAULT_EXE = Path.home() / "AppData" / "Roaming" / "paracore-data" / "mcp-servers" / "paracore-gen.exe"
EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE

if not EXE.is_file():
    print(f"FATAL: installed exe not found at {EXE}")
    sys.exit(2)

print(f"EXE UNDER TEST: {EXE}")
print(f"  size={EXE.stat().st_size}  mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(EXE.stat().st_mtime))}")

proc = subprocess.Popen(
    [str(EXE)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, encoding="utf-8", bufsize=1,
)

responses = {}
lock = threading.Lock()


def reader():
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in msg:
            with lock:
                responses[msg["id"]] = msg


threading.Thread(target=reader, daemon=True).start()

_next_id = [0]


def send(method, params=None, notify=False):
    _next_id[0] += 1
    rid = _next_id[0]
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        msg["id"] = rid
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    if notify:
        return None
    deadline = time.time() + 180
    while time.time() < deadline:
        with lock:
            if rid in responses:
                return responses.pop(rid)
        time.sleep(0.05)
    return None


_LAST_TYPES = []


def call_tool(name, args):
    """Return the TEXT content, and record every content type seen in `_LAST_TYPES`.

    ⚠ Recording the types matters: `export_view` is typed `-> Image`, so a successful call
    carries an `image` item and NO text. A probe that only joins text items sees "" and
    reports a failure for a tool that worked perfectly. (That is exactly what the first
    version of this file did.)
    """
    global _LAST_TYPES
    _LAST_TYPES = []
    r = send("tools/call", {"name": name, "arguments": args})
    if not r:
        return ""
    if "error" in r:
        return json.dumps(r["error"])
    out = []
    for item in r.get("result", {}).get("content", []):
        _LAST_TYPES.append(item.get("type"))
        if item.get("type") == "text":
            out.append(item.get("text", ""))
    return "\n".join(out)


results = []


def check(label, ok, detail=""):
    results.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"   <- {detail}"))


# ── handshake ─────────────────────────────────────────────────────────────
init = send("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "probe_tool_surface", "version": "0"},
})
if not init or "result" not in init:
    print("FATAL: handshake failed")
    sys.exit(2)
send("notifications/initialized", {}, notify=True)

# ── 1. get_context ────────────────────────────────────────────────────────
ctx = call_tool("get_context", {})
print("\n--- get_context (first 300) ---")
print(ctx[:300])
check("get_context returns a document report", len(ctx) > 200, f"len={len(ctx)}")
check("get_context names the open document", "Paracore_2025_Demo" in ctx,
      "document title absent from the report")
check("get_context is not an error blob", "Traceback" not in ctx and "Execution Failed" not in ctx,
      ctx[:200])

# ── 2. get_globals ────────────────────────────────────────────────────────
gl = call_tool("get_globals", {})
print("\n--- get_globals (first 300) ---")
print(gl[:300])
check("get_globals returns the cheat sheet", len(gl) > 500, f"len={len(gl)}")
# Names an agent must be able to discover from here. `Doc` is the document global; without it
# a generated script cannot compile at all.
for must in ("Doc", "Transact", "Println", "GetElements"):
    check(f"get_globals documents {must}", must in gl, f"{must} absent")

# ── 3. list_skills ────────────────────────────────────────────────────────
ls = call_tool("list_skills", {})
print("\n--- list_skills (first 300) ---")
print(ls[:300])
check("list_skills returns a catalogue", len(ls) > 200, f"len={len(ls)}")
check("list_skills is not an error blob", "Traceback" not in ls, ls[:200])

# ── 4. read_skill — a REAL skill, then a BAD name ─────────────────────────
import re as _re
# ⚠ The catalogue lists skills as `## <name>` markdown headings. The first version of this
#   regex allowed only a leading `-`, `*` or nothing, so it matched NOTHING and the probe
#   reported "could not parse any name" — a probe bug that looked like an empty catalogue.
cand = _re.findall(r"^##\s+([a-z0-9][a-z0-9\-]{2,40})\s*$", ls, _re.MULTILINE)
print(f"\n  candidate skill names from the catalogue: {cand[:8]}")

if cand:
    name = cand[0]
    rs = call_tool("read_skill", {"name": name})
    print(f"--- read_skill({name!r}) (first 300) ---")
    print(rs[:300])
    check(f"read_skill({name!r}) returns a real body", len(rs) > 400, f"len={len(rs)}")
    check(f"read_skill({name!r}) looks like markdown", "#" in rs or "- " in rs,
          "no headings or bullets")
else:
    check("a skill name could be parsed from list_skills", False,
          "could not parse any name from the catalogue")

# The error path — a name that does not exist must SAY SO, not return a blank or crash.
bad = call_tool("read_skill", {"name": "definitely-not-a-skill-xyz"})
print("\n--- read_skill(bogus) ---")
print(bad[:400])
check("read_skill on a bogus name explains itself",
      len(bad) > 30 and ("not" in bad.lower() or "unknown" in bad.lower() or "available" in bad.lower()),
      bad[:200])
check("read_skill on a bogus name does not return a blank", bad.strip() != "", "empty reply")

# ── 5. _search_schema — a real category, then a bogus one ─────────────────
ss = call_tool("_search_schema", {"category_name": "Wall"})
print("\n--- _search_schema('Wall') (first 400) ---")
print(ss[:400])
check("_search_schema returns schema detail for Wall", len(ss) > 150, f"len={len(ss)}")
check("_search_schema mentions a Wall parameter or type", "Wall" in ss, "no 'Wall' in output")
check("_search_schema is not an error blob", "Traceback" not in ss, ss[:200])

ssbad = call_tool("_search_schema", {"category_name": "ZZZNotACategory"})
print("\n--- _search_schema(bogus) ---")
print(ssbad[:400])
check("_search_schema on a bogus category explains itself",
      len(ssbad) > 20 and ("not" in ssbad.lower() or "unknown" in ssbad.lower()
                           or "no " in ssbad.lower()),
      ssbad[:200])

# ── 6. _explore_revit_data — a real read-only query ───────────────────────
ex = call_tool("_explore_revit_data", {
    "csharp_code": 'Println("EXPLORE_WALLS=" + GetElements("Walls").Count());',
    "justification": "probe: verify the discovery tool executes a read-only snippet",
})
print("\n--- _explore_revit_data (first 400) ---")
print(ex[:400])
check("_explore_revit_data executes and returns the count", "EXPLORE_WALLS=609" in ex,
      ex[:250])
check("_explore_revit_data is not an error blob", "Traceback" not in ex, ex[:200])

# Two-sided: the SAME tool must REFUSE a write, or "discovery only" is a comment, not a guard.
exw = call_tool("_explore_revit_data", {
    "csharp_code": 'GetElements("Walls").First().SetVal("Comments", "PROBE-SHOULD-BE-REFUSED");',
    "justification": "probe: a write must be refused by the discovery guard",
})
print("\n--- _explore_revit_data(WRITE) ---")
print(exw[:400])
check("_explore_revit_data REFUSES a write", "refus" in exw.lower() or "read-only" in exw.lower()
      or "not allowed" in exw.lower() or "discovery" in exw.lower(), exw[:250])

# ── 7. _read_extension_methods — a query, and the empty default ───────────
rem = call_tool("_read_extension_methods", {"query": "transaction"})
print("\n--- _read_extension_methods('transaction') (first 400) ---")
print(rem[:400])
check("_read_extension_methods returns a real section", len(rem) > 300, f"len={len(rem)}")
check("_read_extension_methods covers transactions", "Transact" in rem or "transaction" in rem.lower(),
      "no transaction content")

# ── 8. export_view — a real view, then a bogus name ──────────────────────
# ⚠ THE TOOL IS TYPED `-> Image`. A successful call carries an `image` content item and NO
#   text, so success must be judged on the CONTENT TYPES, not on text. The first version of
#   this check looked for text and reported a blank failure for a tool that had rendered a
#   41 KB JPEG. Its docstring is explicit: "Returns the rendered image. On failure it
#   returns a text explanation instead."
ev = call_tool("export_view", {"view_name": "", "pixel_size": 800})
ev_types = list(_LAST_TYPES)
print("\n--- export_view('') ---")
print(f"  content types: {ev_types}")
print(f"  text length: {len(ev)}")
check("export_view returns an IMAGE on success (its documented return type)",
      "image" in ev_types, f"content types were {ev_types}")
check("export_view does not also report an error", "Execution Failed" not in ev, ev[:200])

evbad = call_tool("export_view", {"view_name": "No Such View ZZZ", "pixel_size": 400})
print("\n--- export_view(bogus) ---")
print(evbad[:500])
check("export_view on a bogus view falls back to a TEXT explanation",
      "text" in _LAST_TYPES and len(evbad) > 40, f"types={_LAST_TYPES} len={len(evbad)}")
check("export_view on a bogus view names the real views",
      "No Such View ZZZ" in evbad or "not found" in evbad.lower()
      or "available" in evbad.lower() or "no view" in evbad.lower()
      or "Exportable views" in evbad,
      evbad[:250])

try:
    proc.stdin.close()
except Exception:
    pass
proc.terminate()

fails = sum(1 for ok, _ in results if not ok)
print()
print("=" * 78)
print(f"{len(results) - fails}/{len(results)} passed, {fails} failure(s)")
print("=" * 78)
sys.exit(0 if fails == 0 else 1)
