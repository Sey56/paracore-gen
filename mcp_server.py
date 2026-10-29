"""Paracore-Gen — the GENERALIST REPL MCP.

⚠ THIS FILE IS ONLY THE DOMAIN. A name, an instruction block, and (in the specialist
repos) some skills. Everything else — the eight REPL tools, the skill delivery, the
resources, the dialog watcher, the metrics, the C# lint — is the SHARED CORE in
`paracore/mcp/mcp_core/`. Read `paracore/mcp/mcp_core/domain.py` first: it explains the
split, and why the skills are served as TOOLS rather than resources.

⚠ paracore-gen has NO domain skills of its own: it is the generalist, so the SHARED method
skills ARE its whole set — MINUS `create-geometry`. Modelling belongs to `paracore-model`;
this server generates REPL on the fly against the raw Revit API, LINQ and the DSL, and
`GEN_INTRO` states which to prefer. That is the difference between this file and
paracore-model's.
"""

# ── Locate the SHARED MCP CORE — the one in the engine repo (`paracore/mcp`) ──────
# The ONLY thing a domain repo has to know about the core is WHERE IT IS. This block is
# deliberately the one piece of boilerplate each MCP carries: it is the repo's own
# location fact, and nothing about the core's contents is repeated here.
#   frozen  PyInstaller already unpacked the core into sys._MEIPASS, on sys.path.
#   dev     walk up to the sibling `paracore/` checkout and use its `mcp/`.
import os as _os
import sys as _sys

if not getattr(_sys, "frozen", False):
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _dir, _core = _here, None
    for _ in range(6):
        if _os.path.isfile(_os.path.join(_dir, "paracore", "mcp", "mcp_core", "__init__.py")):
            _core = _os.path.join(_dir, "paracore", "mcp")
            break
        _up = _os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(
            "Paracore MCP shared core not found: no `paracore/mcp/mcp_core` above "
            f"{_here}. The core lives in the ENGINE repo, so the repos must be SIBLING "
            "checkouts under one parent directory."
        )
    _sys.path.insert(0, _core)

import logging

# Now we can safely import from the core (it is in base_dir or on sys.path).
from grpc_client import close_channel, init_channel

from mcp_core.bootstrap import domain_root, is_frozen
from mcp_core.domain import Domain
from mcp_core.server import create_server, setup_logging

# In dev this is the repo root; frozen it is sys._MEIPASS — where the bundled
# `skills/`, `prompts/` and engine docs live.
REPO_ROOT = domain_root(__file__)

# ── The domain ────────────────────────────────────────────────────────────────
# ⚠ ONLY what is true of THIS server. GLOBALS / QUERY / FORBIDDEN / PARAMETER NAMES and
# the session ritual are in the core's COMMON_RULES; do not repeat them here.
GEN_INTRO = """THIS SERVER IS THE GENERALIST — you write and run REPL scripts for ANY Revit
  task, not one specialism. Prefer the Paracore extension methods, but the raw
  Revit API, LINQ and .NET are all in scope when the methods are not enough.
  A real building is built PER LEVEL: levels → slabs → walls → rooms — never
  via massing (a Form cannot become a wall, floor or room). `list_skills` is the
  authoritative list of what THIS server teaches: if the recipe you want is not
  among them, it is not here — say so instead of guessing a skill name.
  After every build, re-derive counts and read Doc.GetWarnings()."""

# ── The skill set: the shared method skills, MINUS modelling ──────────────────
# ⚠⚠ `create-geometry` is NOT here (operator, 2026-10-27). **`paracore-model` is what
#   models.** This server's job is to generate REPL on the fly, with full access to the raw
#   Revit API, LINQ and the Paracore DSL — `GEN_INTRO` states which to prefer. A modelling
#   curriculum in the generalist both duplicates paracore-model and reads as a claim that
#   this server specialises in modelling.
#   The other eight ARE the DSL vocabulary the generalist writes in, so they stay.
# ⚠ This filters the CATALOGUE only. The file still lives in the shared core, for the
#   domains that do model — see `Domain.shared_skills` in mcp_core/domain.py.
GEN_SHARED_SKILLS = (
    "query-filter",
    "aggregate-group",
    "parameter-access",
    "write-modify",
    "display-visualize",
    "discovery-debug",
    "identity-orientation",
    "materials-units",
)

DOMAIN = Domain(
    name="Paracore-Gen",
    slug="gen",
    intro=GEN_INTRO,
    root=REPO_ROOT,
    # No domain skills: the generalist serves the eight non-modelling shared method skills.
    shared_skills=GEN_SHARED_SKILLS,
)

# ── Logging ───────────────────────────────────────────────────────────────────
# Write to %APPDATA%\paracore-data\logs\ (created by the Paracore add-in installer),
# NOT to the exe directory — Program Files is not writable without admin.
log_dir = (
    _os.path.join(_os.getenv("APPDATA", ""), "paracore-data", "logs")
    if is_frozen() else REPO_ROOT
)
setup_logging(DOMAIN, log_dir)
logger = logging.getLogger("paracore-mcp")

# ── The server: shared core + this domain ─────────────────────────────────────
# ⚠ `pick_object` no longer exists in ANY domain (operator ruling, 2026-10-28): it was
#   removed from the shared registry, not omitted here. A pick is a GALLERY concern — the
#   target is a typed property in the script's `Params` class
#   (`[Select(SelectionType.Element)] public Wall? TargetWall`) and the gallery UI drives
#   the selection. That is a human clicking a control in a UI that OWNS the control; an MCP
#   agent has no such surface, so `omit_common` has nothing to omit and is not passed.
mcp = create_server(DOMAIN)


if __name__ == "__main__":
    # ── THE SECOND EYE ────────────────────────────────────────────────────────
    # A resident daemon thread that answers Revit's modal failure dialogs from
    # OUTSIDE, so a tool call blocked on a dialog can still complete. It must be
    # started HERE, at boot, and not per call: the call that provokes a dialog is
    # the one that cannot start anything. See mcp_core/dialog_watcher.py.
    # ⚠ It never suppresses a failure and never touches a transaction — it only
    #   presses the button a human would press. Kill switch: PARACORE_WATCH_DIALOGS=0
    try:
        from mcp_core.dialog_watcher import start_dialog_watcher
        if start_dialog_watcher():
            logger.info("Dialog watcher resident (pid=%d).", _os.getpid())
        else:
            logger.info("Dialog watcher not started (disabled or already running).")
    except Exception as _exc:            # never let the watcher stop the server
        logger.warning("Dialog watcher failed to start: %r", _exc)

    init_channel()
    logger.info("Starting Paracore-Gen FastMCP Server via stdio...")
    try:
        mcp.run(transport="stdio")
    finally:
        close_channel()
        logger.info("FastMCP Server closed.")
