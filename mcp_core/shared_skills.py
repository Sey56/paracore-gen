"""The REPL / dynamic-execution skill set — the SAME in every MCP that drives the engine.

⚠ GENERATED — do not edit a copy.
    `paracore-gen/mcp_core/shared_skills.py` is the AUTHORITY. It is generated into every
    other engine-driving MCP by `paracore/scripts/gen-engine-docs.py` (`--check` / `--write`),
    which also generates the nine `mcp_core/skills/<name>/SKILL.md` files it describes. A hand
    edit in `paracore-model` or `paracore-family` is discarded by the next `--write`.

WHY IT IS SHARED
    These nine skills teach the GENERIC engine's own methods (GetElements, WhereParam,
    SetVal, Wall.Create, ...), so there is nothing to specialise — every client that drives
    the engine gets the identical set. A specialist's own DOMAIN skills are declared
    ALONGSIDE this set in that repo's `mcp_server.py` (e.g. `project-modeling`,
    `family-authoring`), and those are not shared.

    A shared skill must therefore be CONTEXT-NEUTRAL. Routing that is true in only one repo
    belongs in that repo's server instructions, not in the skill body.
"""

SHARED_SKILL_DESCRIPTIONS: dict[str, str] = {
    "query-filter":         "Element retrieval, filtering, and sorting — GetElements, WhereParam, WhereMatches, OrderByParam",
    "aggregate-group":      "Grouping, counting, and summing — GroupByParam, SumParam, aggregated totals",
    "parameter-access":     "Reading element parameters — GetStr, GetNum, GetVal, GetInt, type-level accessors",
    "write-modify":         "Modifying elements — SetVal, SetNum, SetParam, Delete, Hide, Isolate, Transact",
    "display-visualize":    "Rendering data — Table, BarGraph, PieGraph, LineGraph, ExportImage (view → image file), Println, Select projection",
    "discovery-debug":      "Exploring unknown elements — CombinedParams, Peek, BuiltInParams, GeometrySummary",
    "create-geometry":      "Creating new Revit elements — Wall.Create, Floor.Create, XYZ, CurveLoop, InputUnit",
    "identity-orientation": "Element identity and door/window data — FamilyName, Matches, RoomFrom, Handing",
    "materials-units":      "Materials, unit conversion, numeric helpers — InputUnit, OutputUnit, IsAlmostEqualTo",
}
