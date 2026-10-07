# Project modeling in paracore-mcp — what to add, and what not to

**Date:** 2026-10-02
**Trigger:** a Claude Desktop session asked to model the Empire State Building from reference
photos and overall dimensions produced a **massing form** — no walls, floors, rooms or levels.
**Question:** can paracore-mcp model real buildings with standard Revit elements?

---

## 1. Verdict

**Yes — and it needs one new tool and one much larger skill. Not ten new tools.**

The capability is already reachable: `Wall.Create`, `Floor.Create` and `NewFamilyInstance` are
documented in `mcp_core/skills/create-geometry/SKILL.md` today, and the engine is a real C# REPL
with the full `Autodesk.Revit.DB` surface. What is missing is **the recipe layer** and **the eyes**.

---

## 2. Why it came out as a massing form — measured, not guessed

| Skill | Size | Recipe depth |
|---|---|---|
| `create-geometry` | **2,816 B** | 4 snippets: Wall, Floor, FamilyInstance, Column |
| `massing-forms` | **10,576 B** | full: `AddProfile`, `AddEdge`, `AddPath`, loft, adaptive |
| `family-authoring` | **38,781 B** | full: extrusions, sweeps, blends, `FamilyManager`, types |

That is a **1 : 3.8 : 13.8** weight ratio. An agent asked to "model a building" reads the catalog,
finds one path with a complete worked recipe, and takes it. The massing path won on documentation
weight — not on capability.

⚠ **This is a routing problem, and it will recur on every building request until the weights change.**
The Empire State screenshot is not a failure of the engine; it is the predictable output of an
uneven skill library.

Note also that massing is a **dead end for a building**: `Form` / `DirectShape` geometry cannot
become floors, walls or rooms. Massing is for concept studies. If the target is a building, massing
should not be the path at all.

---

## 3. The one-tool rule — why not ten typed tools

The Claude Desktop transcript proposes ten typed creation tools (`create_levels`, `create_walls`,
`create_floor`, `create_rooms`, …). **The diagnosis is right; the prescription is wrong.**

1. **A tool is a fixed contract paid for on every turn. A skill is a rich procedure paid for only
   when read.** Ten more tools adds ten more schemas to every request, permanently, to express
   operations the REPL already performs.
2. **A typed tool is strictly *less* capable than the REPL.** `create_walls(polyline, type, level)`
   can only do what its signature allows. `Wall.Create` has overloads for height, offset, flip and
   structural use; a wall along a curved segment; a wall joined to a neighbouring one. Every one of
   those becomes either an extra argument or a limitation.
3. **It contradicts this project's own research.** `Docs/REVIT_MCP_LANDSCAPE.md` §2.6 and §7: the
   most-starred servers consolidate (`puran-water`: 8 tools; `multiCAD`: 56 commands in 7 tools),
   and Horizun at 123 tools had to add *permission profiles* to manage the blast radius. The MCP
   ships **7 tools** today and the standing constraint is *"do not bloat the agent."*

**The correct home for all ten operations is a skill**, in the existing `mcp_core/skills/` pattern.

### The one exception — and it is a real one

**Every existing tool returns text.** `execute_dynamic_query` returns a *summarized string*; the
summarizer truncates tables at 50 rows and text at 20 lines. There is no path by which an agent
using this MCP can *see* what it built.

That is the single capability gap that cannot be closed with a recipe, and it is worth exactly one
new tool.

---

## 4. The one new tool — `export_view`

Renders a named view to an image and returns it as an MCP **image content block**, so a multimodal
agent can look at the model.

### ⚠⚠ The isolation rule decides where this lives

`SchedulesExportService.cs` is **Pro-only** — it sits in the takeoff/Pro surface
(`CROSS-REPO.md`; `_crossrepo_verify.py` lists it under `PRO-ONLY`). Three consequences:

- ❌ The export path must **not depend on it**. A dependency on a Pro-only file is exactly the
  "mixed" state that makes the later free/pro sync hard.
- ❌ It must **not** be implemented *inside* any Pro-only file either.
- ✅ **A capability both tiers should have belongs in a SHARED file — or, better, outside the
  cross-repo split altogether.**

**Chosen design: MCP-side, raw Revit API.** The tool emits a snippet using `ImageExportOptions` /
`Document.ExportImage` — plain `Autodesk.Revit.DB`, present in the free engine and the Pro engine
alike. **Nothing is added to `paracore-pro` at all**, so there is nothing to isolate, nothing to
sync, and nothing to un-mix later. The MCP is not part of the cross-repo split, which makes it the
cleanest possible home for a capability that must work on both tiers.

**The Pro file is still valuable — as EVIDENCE, not as a dependency.** Read it for the settings and
the traps; do not reference it from the MCP, and do not copy Pro code into a shared file.

```csharp
new ImageExportOptions {
    FilePath        = outPath,
    ZoomType        = ZoomFitType.FitToPage,
    FitDirection    = FitDirectionType.Horizontal,
    PixelSize       = 1200,
    ImageResolution = ImageResolution.DPI_150,
    HLRandWFViewsFileType = ImageFileType.PNG,
    ExportRange     = ExportRange.SetOfViews,
};
opt.SetViewsAndSheets(new[] { view.Id });
doc.ExportImage(opt);
```

**Two traps are already documented in that file's own comments — keep them:**
- ⚠ **A shaded view comes out as JPG regardless of the requested `ImageFileType`.** Do not trust the
  requested extension.
- ⚠ **Revit appends the view identity to the `FilePath` base** (`"plan_000.png - plan_000.jpg"`), so
  the real file must be found **by prefix**, newest match — not by the exact name passed in.

### Why this needs no add-in change at all

The C# writes the PNG to a temp path **on the same machine** as the MCP (localhost gRPC). The tool
then reads that path and returns `mcp.server.fastmcp.Image(path=...)`.

⇒ **No engine edit, no add-in rebuild, no `sync-shared.ps1`, no `$proOnly` entry.** The only rebuild
is the MCP's own exe — the lightest loop in the workspace.

### The alternative — and what it would cost

Promoting the export to a **shared engine script-API method** (e.g. `Globals/ViewExportExtensions.cs`)
would give *every* consumer the capability — the help site, the VS Code copilot, `paracore-examples` —
not just the MCP. It is a legitimate option, and it stays cleanly syncable because it would be its own
**shared** file.

But it is a different class of change, and it should be a deliberate decision, not a side effect:

| | MCP-side (chosen) | Shared engine method |
|---|---|---|
| Isolation risk | **none** — nothing added to pro | low, **if** it is its own shared file |
| Propagation | MCP exe only | **Class C** — `EXTENSION_METHODS.md`, `REPL_GUIDE.md`, `mcp_core/prompts/*`, `mcp_core/skills/*`, help site, `_api_surface_check.py` |
| Engine rebuild + install | no | **yes** — `install-engine.cmd`, run by the user, Revit closed |
| Consumers | the MCP | every script author |
| Status | — | **engine work is currently PAUSED** (go-to-market) |

**Recommendation: MCP-side now.** It gets the capability onto both tiers immediately, and promoting it
to the engine later is a small, well-understood Class A change with its own file — the sync stays easy
precisely because nothing was mixed in the first place.

**Verified present in the bundled runtime:**
`mcp-build/.venv/Lib/site-packages/mcp/server/fastmcp/utilities/types.py:9` defines `Image`, and
`mcp/server/fastmcp/__init__.py:11` exports it (`__all__ = ["FastMCP", "Context", "Image", …]`).
`Image(path=...)` base64-encodes the file and produces `ImageContent(type="image", …)`.

⇒ **MCP-only work. No add-in rebuild, no Revit restart, no engine edit.**

### Design notes

- **Do not route through the user-facing summarizer.** Build the snippet, call the gRPC `ExecuteRepl`
  directly (as `explore_revit_data` does) and read the path from **`structured_output`** — per
  `paracore-pro` MEMORY rule 18, a *value* comes from `structured_output`; `output` is a transcript
  that accumulates `Println` and may truncate.
- **Camera control is a separate, later question.** `ViewOrientation3D` on a `View3D` gives
  "SE corner, 30° elevation". A first version should export *whatever view is named* and leave
  camera placement to a follow-up.
- **Add it to the tool list only if it earns its keep.** Seven tools is the current budget; eight is
  the first real increase. It earns it — an agent that cannot see cannot do photo-to-model.

---

## 5. The skill — `project-modeling`

A new skill beside `create-geometry` (which stays as the single-element reference). Build order
follows §6 of the transcript, which is correct: **per level, not massing.**

| # | Recipe | API | Known trap |
|---|---|---|---|
| 1 | Levels | `Level.Create(Doc, elev)` | ⚠ creating a level does **not** create a plan view |
| 2 | Plan views | `ViewPlan.Create(Doc, vftId, levelId)` | needs a `ViewFamilyType` whose `ViewFamily == FloorPlan` |
| 3 | Grids | `Grid.Create(Doc, Line)` | name them, or every downstream reference is positional |
| 4 | Footprint loop | `CurveLoop` | ⚠⚠ **validate closure explicitly** — "Curve loops do not satisfy the input requirements" is a non-closure / non-planarity error. Compare first vs last point and report the gap **in mm**, do not surface the raw message |
| 5 | Floor slab | `Floor.Create(Doc, loops, typeId, levelId)` | slab sits *above* its level by default |
| 6 | Walls | `Wall.Create(Doc, line, typeId, levelId, height, offset, flip, structural)` | the height overload avoids a level-to-level chain |
| 7 | Curtain walls | `Wall.Create` with a curtain `WallType`; `CurtainGrid.AddGridLine` | panel/mullion types are separate from the wall type |
| 8 | Roof / terrace | `Doc.Create.NewFootPrintRoof(...)` | ⚠ needs a **plan-view sketch plane**, not a 3D view |
| 9 | Rooms | `Doc.Create.NewRoom(level, UV)` + `NewRoomBoundaryLines` | ⚠ `Room.Area` stays **0** until boundaries close — check it, do not report 0 as a result |
| 10 | Doors / windows | `NewFamilyInstance(hostWall, point, level, NonStructural)` | the point must lie on the wall's location curve |
| 11 | Stairs | `StairsEditScope` + `Stairs.CreateSketchedStairs` | heaviest recipe; scope it last |
| 12 | Columns / beams | `NewFamilyInstance(..., StructuralType.Column / Beam)` | a beam needs `Line` + level, not just a point |
| 13 | Type duplication | `WallType.Duplicate(name)` + `SetCompoundStructure(CreateSimpleCompoundStructure(layers))` | layer widths are in feet |
| 14 | Family loading | `Doc.LoadFamily(path, out Family)` | ⚠ a load does **not** activate a symbol — `symbol.Activate()` first |

### Traps already paid for — carry them into the skill

From the Claude Desktop session, and they are real:
- ⚠ **`Color` is ambiguous** between `System.Drawing.Color` and `Autodesk.Revit.DB.Color`. Qualify it.
- ⚠ **`Revolve` failed where a blend worked.** Prefer the construction that is proven.
- ⚠ **Work in internal feet; report with `OutputUnit`.** Already covered by `materials-units`, but
  building-scale recipes are where it bites hardest.

---

## 6. Verification — three tiers

| Tier | What | Home | Cost |
|---|---|---|---|
| 1 | counts, volumes, bbox extents, `Doc.GetWarnings()` after every build | **recipe**, always on | free |
| 2 | look at it — `export_view` | **the one new tool** | one image |
| 3 | spec-vs-model pass/fail table (expected heights / areas / counts) | **recipe** | free |

Tier 1 and Tier 3 are the project's own standard: *a number you cannot re-derive is not a result.*
A building "created" is not a result; **"42 walls, 7 levels, 1,280 m² of slab, 0 warnings"** is.

---

## 7. Safety — all three are recipes, no tools needed

| Want | How | Note |
|---|---|---|
| Checkpoint | `Doc.SaveAs` to a timestamped path **before** a bulk operation | the model was lost to a single undo this session |
| Tagged batch | stamp created elements with a batch id in a **shared parameter** | lets you say "replace batch ESB-v3" instead of deleting by name prefix |
| Dry-run | count and print the planned operations, commit only on the second call | mirrors the existing bulk-delete warning — the right instinct |

⚠ Deleting a batch is **still a delete**. Under the user's standing rule: list the paths/ids, say how
many, and get an explicit confirmation. A tagged batch makes this *safer*, not automatic.

---

## 8. Discovery

Partly there already:
- `_search_schema(category)` — parameter names, cached.
- `get_context` — active view, selection, **levels with elevations**.
- Unused RPCs: the proto defines **26 RPCs** and the MCP calls **3**. `GetModelCategories` and
  `GetCategoryParameters` are reachable if a type inventory proves too slow in the REPL.

Missing, and cheap as **recipes**: list available `WallType` / `FloorType` / `RoofType` /
`CurtainSystem` types; list `FamilySymbol`s; load a family from a path. All are `GetElements<T>()`
one-liners.

---

## 9. The spec layer — not the MCP's job

The transcript's §5 (a written spec: site, grids, levels, floor plates, facade type, opening
rhythm; each value tagged *measured* or *estimated* with a confidence) is **correct and important** —
and it belongs to **the agent**, not to the MCP. The MCP has no opinion about what a building should
be.

The MCP's contribution is to make the spec **checkable**: a recipe that reads a spec table and diffs
it against the model, returning pass/fail per row. That is Tier 3 above.

For photos, the scale-anchor method is right: ask for **one or two real dimensions** (a floor height,
a door width) and derive the rest. Do not guess a footprint from pixels — that is exactly the
"60 ft on all sides" conflict from the session.

---

## 10. What NOT to do

- ❌ **No ten typed creation tools.** Sprawl; the landscape doc is explicit.
- ❌ **No massing as the building path.** A `Form` cannot become a room. Keep `massing-forms` for
  concept studies only, and say so in its own first line.
- ❌ **No computer use as a hand.** Already researched — `Docs/REVIT_COMPUTER_USE_RESEARCH.md` §7:
  it belongs as a **camera**, and even then `ExportImage` is deterministic and better.
- ❌ **No engine change.** Nothing in this plan requires touching `CoreScript.Engine`. That is
  deliberate: engine work is the heaviest loop and reaches three clients.
- ❌ **No Pro / takeoff scope.** Building modeling is generalist Revit and in scope; BOQ, quantities
  and watchdogs are not.

---

## 11. Sequencing, by build loop

**Track A — MCP only (Markdown). No rebuild, no Revit restart.**
1. `project-modeling` skill — recipes 1–14 above, with the traps.
2. Correct `massing-forms`' opening line to state it is concept-only.
3. Verification recipes (Tier 1 and Tier 3) into the skill.

**Track B — MCP Python. Rebuild + reinstall the MCP exe (no add-in, no engine).**
4. `export_view` tool + `Image` return.
5. Then, and only then, consider camera placement (`ViewOrientation3D`).

⚠ **Neither track touches `paracore-pro`.** Both tiers get the capability because the export uses
raw Revit API, not a tier-specific method — so there is no `$proOnly` entry to add, no
`sync-shared.ps1` run, and nothing to extract later. If the capability is ever promoted to the
engine (§4), it becomes its own **shared** file, which syncs cleanly.

**Track C — engine.**
6. **Empty.** Nothing here needs it.

⚠ Track A and Track B both change files **bundled inside the MCP exe**. Per the project's own
standing trap: a skill edit is invisible to the agent until `build-mcp.ps1` + install + restart, and
liveness must be proved by reading the `skill://…` resource off the running server — an mtime only
proves a build *may* have run.

---

## 12. Open questions — verify, do not assume

1. Does `Image` survive the **PyInstaller** bundle? It is imported from `mcp.server.fastmcp`, which
   is already bundled — but `mcp_core/prompts/*.md` is *not* bundled (see the open defect in
   MEMORY.md), so bundling has surprised this project before. **Prove it on the installed exe.**
2. ⚠⚠ **THE DESIGN-CRITICAL ONE: does `doc.ExportImage` work from the REPL's
   `AssemblyLoadContext`?** The Pro path calls it from the add-in's own context, inside a
   `Transaction`. If it fails in the sandboxed script ALC, the whole MCP-side design falls over and
   §4's alternative becomes the only route. **Probe this first — it is one call.**
   Also confirm it works with **no transaction open** (an export is not a model change).
3. Is `SetViewsAndSheets` enough for a **3D view**, or does it need `ExportRange.CurrentView`?
4. `ViewPlan.Create` needs a `ViewFamilyType` — is one reliably present in a default template?

Each of these is a small REPL probe, not a design question.

---

## Sources (all in-repo)

- `mcp_core/skills/create-geometry/SKILL.md` — the 2,816 B stub
- `mcp_core/skills/massing-forms/SKILL.md`, `.../family-authoring/SKILL.md` — the weight comparison
- `paracore-pro/Paracore.Addin/Services/SchedulesExportService.cs:798-831` — working `ExportImage`
- `Docs/FAMILY_EDITOR_PLAN.md:135-161` — view export already proposed; "camera, not a hand"
- `Docs/REVIT_MCP_LANDSCAPE.md` §2.6, §4.5, §7 — consolidation, procedures, strategic read
- `Docs/REVIT_COMPUTER_USE_RESEARCH.md` §7 — where computer use belongs
- `mcp-build/.venv/.../mcp/server/fastmcp/utilities/types.py:9` — `Image` → `ImageContent`
