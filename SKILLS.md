# Paracore Method Skills

Nine operation-based skills. Read `query-filter` first (always needed), then pull others as the task demands.

⚠ This MCP is the **generalist** — it generates and runs REPL scripts for *any* Revit task. These nine
skills cover the Paracore **extension methods**; the raw Revit API, LINQ and .NET are always in scope
when the methods are not enough. Deep **modelling** and **family (.rfa)** recipes live in the
`paracore-model` and `paracore-family` MCPs.

---

<!-- GENERATED:SHARED-SKILLS:BEGIN -->
⚠ **GENERATED — do not edit this region.** These nine are the **shared REPL / dynamic-execution set**: they teach the GENERIC engine's own methods, so they are identical in every engine-driving MCP. Authority: `paracore/mcp/mcp_core/shared_skills.py` — the shared MCP core, which every MCP IMPORTS instead of copying. The full text of each lives in `paracore/mcp/mcp_core/skills/<name>/SKILL.md`.

## query-filter

Element retrieval, filtering, and sorting — GetElements, WhereParam, WhereMatches, OrderByParam

**When:** Always. Every query starts here.
**Detail:** `query-filter/SKILL.md`

## aggregate-group

Grouping, counting, and summing — GroupByParam, SumParam, aggregated totals

**When:** "How many per type?", "Total volume?", any aggregation.
**Detail:** `aggregate-group/SKILL.md`

## parameter-access

Reading element parameters — GetStr, GetNum, GetVal, GetInt, type-level accessors

**When:** Reading any data from elements.
**Detail:** `parameter-access/SKILL.md`

## write-modify

Modifying elements — SetVal, SetNum, SetParam, Delete, Hide, Isolate, Transact

**When:** Any modification request.
**Detail:** `write-modify/SKILL.md`

## display-visualize

Rendering data — Table, BarGraph, PieGraph, LineGraph, ExportImage (view → image file), Println, Select projection

**When:** Rendering results — or looking at the model.
**Detail:** `display-visualize/SKILL.md`

## discovery-debug

Exploring unknown elements — CombinedParams, Peek, BuiltInParams, GeometrySummary

**When:** "What parameters does this element have?", first time with a category.
**Detail:** `discovery-debug/SKILL.md`

## create-geometry

Creating new Revit elements — Wall.Create, Floor.Create, XYZ, CurveLoop, InputUnit

**When:** Any creation — a wall/floor/door/column.
**Detail:** `create-geometry/SKILL.md`

## identity-orientation

Element identity and door/window data — FamilyName, Matches, RoomFrom, Handing

**When:** Identifying what something is, door schedules, orientation queries.
**Detail:** `identity-orientation/SKILL.md`

## materials-units

Materials, unit conversion, numeric helpers — InputUnit, OutputUnit, IsAlmostEqualTo

**When:** Material queries, unit conversion, geometry comparisons.
**Detail:** `materials-units/SKILL.md`
<!-- GENERATED:SHARED-SKILLS:END -->

---

## Typical Usage Patterns

**Simple query** ("list all doors on Level 1"):
query-filter + display-visualize

**Aggregation** ("room area per level"):
query-filter + aggregate-group + display-visualize

**Modification** ("set fire rating on all Level 1 walls"):
query-filter + write-modify + display-visualize

**Exploration** ("what parameters do these columns have?"):
query-filter + discovery-debug + display-visualize

**Creation** ("place a 900mm door on Level 1"):
query-filter + create-geometry + write-modify (for parameters)

**Door schedule** ("door schedule with handing"):
query-filter + identity-orientation + display-visualize

**Material query** ("what material are these walls?"):
query-filter + materials-units + display-visualize

**Check the build looks right** ("does this look right?"):
export_view with `annotations: "tags"` + display-visualize
⚠ The default `annotations: "model"` HIDES every dimension and tag. If the task involves
dimensions, tags or room names, ask for `"tags"` — otherwise you are checking geometry blind to
the part the user actually cares about.

**Anything else** — this server is the generalist: write and run a REPL script with the extension
methods, or drop to the raw Revit API / LINQ when they are not enough.
⚠ **Modelling a building** ("model this building", "make it 3 storeys", "build this floor plan with
its dimensions and room tags") → the **`paracore-model`** MCP. **Family / conceptual mass**
("make a family", "loft this profile into a mass") → the **`paracore-family`** MCP.
