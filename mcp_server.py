import os
import sys

# Handle PyInstaller bundle paths
if getattr(sys, 'frozen', False):
    # In a bundle, the root is sys._MEIPASS
    base_dir = sys._MEIPASS
    # Add the base directory to path so internal imports work
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
else:
    # In development mode, mcp_server.py is at paracore-gen root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

def _get_resource_path(filename: str) -> str:
    """Resolve a bundled resource file path for both frozen and dev modes."""
    if getattr(sys, 'frozen', False):
        # PyInstaller extracts --add-data files into sys._MEIPASS
        return os.path.join(sys._MEIPASS, filename)
    else:
        # Dev mode: docs are alongside mcp_server.py in paracore-gen root
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

import json
import logging
from mcp.server.fastmcp import FastMCP, Image

# Now we can safely import from grpc_client (which is in base_dir/server or base_dir)
from grpc_client import close_channel, init_channel

# ── Shared tool implementations (single source of truth) ──────────────────
# Previously: try/except import of individual helpers with silent no-op fallback.
# Now: direct import from mcp_core — if this fails, the server fails LOUD.
from mcp_core.prompt_assembler import build_prompt
from mcp_core.tools import (
    explore_revit_data,
    execute_dynamic_query,
    search_schema,
    read_extension_methods,
    get_globals,
    get_context_report,
    pick_object_report,
    export_view_report,
    ping as ping_impl,
    _SESSION,
)
from mcp_core.metrics import init as init_metrics

def _get_skill_path(skill_name: str) -> str:
    """Resolve a skill directory path for both frozen and dev modes."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "mcp_core", "skills", skill_name)
    else:
        return os.path.join(base_dir, "mcp_core", "skills", skill_name)

# Configure logging
# Write to %APPDATA%\paracore-data\logs\ (created by Paracore add-in installer)
# NOT to the .exe directory — Program Files is not writable without admin.
if getattr(sys, 'frozen', False):
    log_dir = os.path.join(os.getenv("APPDATA", ""), "paracore-data", "logs")
else:
    log_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "paracore_gen.log")

from logging.handlers import RotatingFileHandler
_mcp_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
_mcp_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
_mcp_handler.setLevel(logging.INFO)

logger = logging.getLogger("paracore-gen")
logger.setLevel(logging.INFO)
logger.addHandler(_mcp_handler)
logger.info(f"MCP Logging initialized at {log_file}")
init_metrics(log_dir)

# Initialize FastMCP Server
# Server-level instructions: injected into LLM context on EVERY turn.
# This is the nuclear option — critical anti-patterns the LLM MUST know
# before writing any code, even if it skips _ping and _read_extension_methods.
mcp = FastMCP(
    "Paracore-Gen",
    instructions="""CRITICAL RULES — violations will be rejected:

GLOBALS (use EXACTLY these — PascalCase):
  Doc (NOT doc, NOT ActiveDocument, NOT activeDocument)
  ActiveView, Selection, Println()

QUERY (use Paracore methods, NOT raw Revit API):
  GetElements("Walls")  — NOT new FilteredElementCollector(Doc)
  GetElements<Wall>()   — typed retrieval
  .WhereParam("Name", "value")  — NOT .Where(e => e.Property)
  .Table()  — NOT foreach+Println loops

FORBIDDEN — these WILL fail:
  new FilteredElementCollector(...)  → use GetElements()
  doc / ActiveDocument               → use Doc
  LookupParameter / get_Parameter    → use .GetStr() / .GetNum()
  .AsString() / .AsDouble()          → use .GetStr() / .GetNum()
  Console.WriteLine()                → use Println()

PARAMETER NAMES — NEVER GUESS:
	  Revit parameters use spaces: "Fire Rating" NOT "FireRating",
	  "Base Constraint" NOT "BaseConstraint", "Top Offset" NOT "TopOffset"

	  CRITICAL — "Level" is NOT universal. It only works for Rooms, Doors,
	  Windows. Walls use "Base Constraint". Columns use "Base Level". Beams
	  and Structural Framing use "Reference Level". GetStr("Level") on a Wall
	  silently returns empty — no error, just blank. Same for GroupByParam.

	  Discovery BEFORE filtering or grouping:
	    → _search_schema("Category") for fast schema lookup
	    → .First().CombinedParams().Table() for live parameter names + values
	    → .CombinedParams().Table() shows instance, type, AND native params
	  A mistyped name returns empty — indistinguishable from "no matches."
	  NEVER guess parameter names. Discover first on the actual category.

MODELLING A BUILDING — read skill://project-modeling FIRST:
  A real building is built PER LEVEL: levels → slabs → walls → rooms.
  Do NOT use massing-forms for a building — a Form cannot become a wall,
  floor or room. Massing is concept studies only.
  After every build, re-derive counts and read Doc.GetWarnings().

START EVERY SESSION WITH:
  1. ping  → verifies the connection for real. If it reports NO CONNECTION, stop
             and tell the user what to fix. Do not attempt Revit operations.
  2. get_context  → active view, current selection, project levels
  3. Read paracore://skills  → skill catalog (which skills cover which operations)
  4. Read the skill resources relevant to the user's request
  5. Then explore. Never write code before reading the relevant skills.

NEVER RETRY BLINDLY:
  Revit's API is single-threaded. Repeating a failed or slow call queues behind the
  one still running and can wedge Revit until it is restarted. If a call reports
  REVIT IS BUSY or a timeout, STOP — wait, ask the user to check Revit for a dialog,
  then confirm Revit responds with a small query."""
)

# Cache resource files in memory at startup (read once, serve from RAM)
_CACHED_SYSTEM_PROMPT: str | None = None
_CACHED_REPL_GUIDE: str | None = None
_CACHED_EXTENSION_METHODS: str | None = None
_CACHED_SKILLS: str | None = None


def _load_resource(path: str, cache: str | None) -> str:
    """Load and cache a resource file. Returns cached copy on subsequent calls."""
    if cache is not None:
        return cache
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return f"Resource not found: {path}"

# Eagerly load resources at startup (prevent LLM from fetching full 32K docs at runtime)
_CACHED_REPL_GUIDE = _load_resource(_get_resource_path("REPL_GUIDE.md"), None)
_CACHED_EXTENSION_METHODS = _load_resource(_get_resource_path("EXTENSION_METHODS.md"), None)
_CACHED_SKILLS = _load_resource(_get_resource_path("SKILLS.md"), None)
logger.info(f"MCP resources cached: REPL_GUIDE={len(_CACHED_REPL_GUIDE)} chars, EXTENSION_METHODS={len(_CACHED_EXTENSION_METHODS)} chars, SKILLS={len(_CACHED_SKILLS)} chars")

@mcp.tool()
def ping() -> str:
    """
    Verify the Paracore MCP server is alive AND that Revit is genuinely reachable.
    Always call this first at the start of every session.

    Reports one of four states, each needing a different fix:
      * connected                     — safe to proceed
      * server up, no document        — Revit is open but no project is loaded
      * Revit running, no connection  — the in-Revit Paracore server is toggled off
      * Revit not running             — start Revit

    Returns the quick-start cheat sheet ONLY when genuinely connected. If this reports
    NO CONNECTION, do not attempt any Revit operation — every call will fail. Tell the
    user what to fix and call ping again.
    """
    _SESSION.record_ping()
    return ping_impl()


@mcp.tool()
def get_context() -> str:
    """
    Get the current Revit context: project, active view, current selection, and levels.

    Call this early, right after ping. Without it you do not know which view is active,
    what the user has selected, or which levels exist — and 'the walls' or 'this level'
    in a request will be guesses.

    Use the returned element Ids directly with execute_dynamic_query or explore_revit_data.
    Levels include their elevations, so you can place or filter by height without a
    separate query.

    Cheap and read-only. No arguments.
    """
    _SESSION.record_discovery()
    return get_context_report()


@mcp.tool()
def pick_object(selection_type: str = "Element", category_filter: str = "") -> str:
    """
    Ask the user to click an element in Revit, and get that element back.

    Use when the request refers to something by pointing rather than by name — "this wall",
    "the column I have open", "select the one I mean". Faster and less ambiguous than
    asking the user to describe an element or read out an Id.

    BLOCKS until the user picks or presses Escape (up to ~2 minutes). Revit's UI is held
    during the pick, so tell the user to click in Revit before calling this, or they will
    not know to act.

    Args:
        selection_type: "Element" (default), "Face", or "Edge".
        category_filter: optional Revit category name to restrict what can be picked,
            e.g. "Walls", "Doors", "Structural Columns".

    Returns the picked element's Id, or a clear message if the user cancelled.
    """
    _SESSION.record_discovery()
    return pick_object_report(selection_type, category_filter)


@mcp.tool()
def export_view(view_name: str = "", pixel_size: int = 1200) -> Image:
    """
    Render a Revit view to an image and return it, so you can SEE the model.

    Use this whenever the request is visual — "does this look right?", "check the
    proportions", "show me what you built" — and after every build stage, not only at
    the end. A picture catches a wall in the wrong place long before a count would.

    Args:
        view_name: name of the view to export, e.g. "3D View - {3D}" or "Level 1".
            Omit it to export the ACTIVE view. Matched case-insensitively; a view
            template cannot be exported.
        pixel_size: longest-edge pixel size. Default 1200; 2000 for detail.

    Returns the rendered image. On failure it returns a text explanation instead — most
    often the named view does not exist, in which case the message lists views that do.

    ⚠ Seeing is not measuring: an image shows a wrong proportion, never a wrong quantity.
    Pair it with the count check (GetElements(...).Count(), Doc.GetWarnings()).
    ⚠ Annotation is SUPPRESSED for this export. Revit's image export does NOT clip
    annotation to the view, so level heads, grid bubbles and elevation/section marks are
    drawn wherever they sit — and because the whole extent is fitted to the page, they
    SHRINK the subject. That is not limited to 3D views: a plan view with elevation
    markers beside it renders the building into a fraction of the frame. The engine hides
    the whole annotation set for the export and restores it, so the picture frames the
    MODEL. To keep the tags, export in-script with
    `ExportImage(path, view, px, hideAnnotation: false)`.
    """
    result = export_view_report(view_name, pixel_size)
    if result.get("path"):
        return Image(path=result["path"])
    return result.get("error") or "The view export failed."


@mcp.tool()
def _explore_revit_data(csharp_code: str, justification: str) -> str:
    """
    Execute a READ-ONLY C# snippet in Revit to explore model data.
    Use this to DISCOVER parameter names, check element counts, verify values
    exist, or inspect schema — anything that DOES NOT modify the model.

    Do NOT use this for modifications. Use execute_dynamic_query for writes.

    The 'csharp_code' must be valid C# top-level statements. The engine has
    all Revit namespaces pre-imported. Prefer Paracore extension methods
    (.GetStr, .WhereParam, .GroupByParam, .Table, etc.) over raw LINQ and
    FilteredElementCollector.

    OUTPUT: Summarized results — tables show up to 50 rows (all rows if the table is
    that small or smaller) plus a total count, text output shows the first 20 lines.
    Charts report their type. Empty results return "No results found" with the query
    context. If a table is truncated you will be told how many rows were hidden.

    FAILURE: Returns a structured error with the error type, line number,
    and a suggested fix. Common failures: wrong parameter name (run
    search_schema first), missing Transact() around a foreach loop, or
    accidentally including write operations (SetVal, Delete) in read-only mode.

    If a call reports REVIT IS BUSY, do not retry it. Wait for the running operation
    to finish — a retry queues behind it and can wedge Revit.
    """
    return explore_revit_data(csharp_code, justification)


@mcp.tool()
def _execute_dynamic_query(csharp_code: str, justification: str) -> str:
    """
    Execute C# in Revit — supports both reads AND writes. This is the tool
    for the user's FINAL action after discovery is complete.

    Do NOT use this for initial exploration — use explore_revit_data or
    search_schema first. This tool is ONLY for the final result after
    discovery is complete. Unlike explore_revit_data, this tool runs
    without read-only restrictions and supports model modifications.

    WRITE OPERATIONS (auto-transact — no Transact() needed):
      Single element: .SetVal("Comments","Done"), .SetNum("Offset",-150,"cm"),
        .Delete(), .Hide(), .Unhide(), .Isolate()
      Collection bulk (one transaction): .SetParam("Comments","Done"),
        .Delete(), .Hide(), .Unhide(), .Isolate()

    Manual foreach loops with writes MUST wrap in Transact("name", () => {...}).

    DISPLAY: Always use .Table() for data, never foreach+Println loops.
    For .Select() tables, include Id as the first column.

    OUTPUT: Summarized — tables (up to 50 rows, or every row if the table is that small
    or smaller, plus a total), text (first 20 lines), charts (type reported). Write
    operations include a confirmation message.

    FAILURE: Structured error with type, line number, and suggested fix.
    Common failures: wrong parameter name, missing Transact() on foreach, or trying
    to chain .Select() after .GroupByParam() (chain .Table() directly instead).

    Fix the reported cause, then retry ONCE with the correction. Do not repeat an
    identical call — if it failed once it will fail the same way. If a call reports
    REVIT IS BUSY, do not retry at all: the retry queues behind the operation that is
    still running and repeated retries can wedge Revit until it is restarted.
    """
    return execute_dynamic_query(csharp_code, justification)


@mcp.tool()
def _search_schema(category_name: str) -> str:
    """
    Fast parameter schema lookup for a Revit category. Use this INSTEAD of
    explore_revit_data when you just need to know what parameters exist for
    a category — it's faster and cheaper than running live C#.

    PREFERRED for discovery. Results are cached in memory after the first
    call per category — instant on subsequent calls.

    'category_name' is a Revit category string. Common values: "Rooms",
    "Walls", "Doors", "Floors", "Ceilings", "Windows", "Structural Columns",
    "Structural Framing", "Ducts", "Pipes". For unknown categories, use
    GetMagicNames() via explore_revit_data to discover available names.

    OUTPUT: A compact list of parameter names with storage types (String,
    Double, Integer, ElementId) and scope (Instance / Type). Copy ONLY the
    parameter name — do NOT include [String] or [Double] annotations in
    your code.

    FAILURE: If the category is not found, returns an error suggesting you
    try explore_revit_data with .CombinedParams().Table() instead. This is
    rare — most standard Revit category names work directly.
    """
    return search_schema(category_name)


@mcp.tool()
def _read_extension_methods() -> str:
    """
    Returns the complete Paracore Extension Methods reference (~17,000 chars —
    the whole catalog, not a summary).

    PREFER reading skill resources instead (skill://{name}/SKILL.md) — a single
    skill is 2–12 KB and covers one operation, so it is far cheaper than pulling
    the full catalog. Use this tool only when you need everything at once.

    Call with NO arguments. Always returns the full catalog.
    """
    return read_extension_methods()


# ── System prompt resource ──────────────────────────────────────────────
# Prompt content lives in agent/prompts/*.md — single source of truth.
# Previously: 131-line MCP_SYSTEM_PROMPT inline string + import from agent.prompt.
# Now: assembled from composable .md files via prompt_assembler.build_prompt().

_MCP_SYSTEM_PROMPT: str | None = None


@mcp.resource("paracore://system-prompt")
def read_system_prompt() -> str:
    """Paracore REPL method catalog and rules. Read this FIRST before using any tools."""
    global _MCP_SYSTEM_PROMPT
    if _MCP_SYSTEM_PROMPT is not None:
        return _MCP_SYSTEM_PROMPT
    _MCP_SYSTEM_PROMPT = build_prompt()
    return _MCP_SYSTEM_PROMPT


@mcp.resource("paracore://globals")
def read_globals() -> str:
    """Complete list of globals, methods, and pre-imported namespaces. Use when unsure what variables/types are available."""
    return get_globals()


# ── End of inline MCP_SYSTEM_PROMPT replacement ──────────────────────────


@mcp.resource("paracore://skills")
def read_skills_catalog() -> str:
    """Skill catalog — which skills cover which operations. Read this FIRST to discover what methods are available, then read the specific skill:// resources you need."""
    global _CACHED_SKILLS
    path = _get_resource_path("SKILLS.md")
    _CACHED_SKILLS = _load_resource(path, _CACHED_SKILLS)
    return _CACHED_SKILLS

@mcp.resource("paracore://repl-guide")
def read_repl_guide() -> str:
    """The authoritative REPL Guide describing magic category hydration strings and retrieval shortcuts."""
    global _CACHED_REPL_GUIDE
    path = _get_resource_path("REPL_GUIDE.md")
    _CACHED_REPL_GUIDE = _load_resource(path, _CACHED_REPL_GUIDE)
    return _CACHED_REPL_GUIDE

@mcp.resource("paracore://extension-methods")
def read_extension_methods() -> str:
    """The complete technical reference for all fluent element getters/setters, properties, and formatting tools."""
    global _CACHED_EXTENSION_METHODS
    path = _get_resource_path("EXTENSION_METHODS.md")
    _CACHED_EXTENSION_METHODS = _load_resource(path, _CACHED_EXTENSION_METHODS)
    return _CACHED_EXTENSION_METHODS

# ── Skills — progressive method discovery ─────────────────────────────────
# Nine operation-based skills. Each is a plain @mcp.resource under skill:// URIs.
# Pre-loaded at startup, served from RAM. Claude Desktop discovers them automatically.

_SKILL_DESCRIPTIONS: dict[str, str] = {
    "query-filter":       "Element retrieval, filtering, and sorting — GetElements, WhereParam, WhereMatches, OrderByParam",
    "aggregate-group":    "Grouping, counting, and summing — GroupByParam, SumParam, aggregated totals",
    "parameter-access":   "Reading element parameters — GetStr, GetNum, GetVal, GetInt, type-level accessors",
    "write-modify":       "Modifying elements — SetVal, SetNum, SetParam, Delete, Hide, Isolate, Transact",
    "display-visualize":  "Rendering data — Table, BarGraph, PieGraph, LineGraph, ExportImage (view → image file), Println, Select projection",
    "discovery-debug":    "Exploring unknown elements — CombinedParams, Peek, BuiltInParams, GeometrySummary",
    "create-geometry":    "Creating new Revit elements — Wall.Create, Floor.Create, XYZ, CurveLoop, InputUnit",
    "project-modeling":   "Modelling a REAL building, per level — levels, plan views, grids, slabs, walls, curtain walls, roofs, rooms, doors/windows, stairs, columns, wall-type duplication, family loading, plus per-build verification and safety recipes. The path for \"model a building\" — NOT massing.",
    "identity-orientation": "Element identity and door/window data — FamilyName, Matches, RoomFrom, Handing",
    "materials-units":    "Materials, unit conversion, numeric helpers — InputUnit, OutputUnit, IsAlmostEqualTo",
    "family-authoring":   "Creating and editing loadable families (.rfa) — NewFamilyDocument, EditFamily, extrusions, revolutions, sweeps, blends, FamilyManager parameters and types",
    "massing-forms":      "Conceptual massing with Form objects — AddProfile, AddEdge, AddPath, FormUtils, loft forms, profile editing, adaptive components",
}

_SKILL_CACHE: dict[str, str] = {}

for _name in _SKILL_DESCRIPTIONS:
    _path = _get_skill_path(_name) + "/SKILL.md"
    _SKILL_CACHE[_name] = _load_resource(_path, None)

def _make_skill_resource(name: str, description: str):
    @mcp.resource(f"skill://{name}/SKILL.md", description=description)
    def _skill() -> str:
        return _SKILL_CACHE.get(name, f"Skill not found: {name}")
    return _skill

for _name, _desc in _SKILL_DESCRIPTIONS.items():
    _make_skill_resource(_name, _desc)

# Prompts
@mcp.prompt()
def analyze_revit_model() -> str:
    """Prompt template for analyzing the current Revit model Health."""
    return "First, read paracore://system-prompt for the complete Paracore method catalog. Then explore the Revit model."

if __name__ == "__main__":
    init_channel()
    logger.info("Starting Paracore FastMCP Server via stdio...")
    try:
        mcp.run(transport="stdio")
    finally:
        close_channel()
        logger.info("FastMCP Server closed.")
