# Modelling refinement — the floor-plan session, verified

**Date:** 2026-10-08
**Trigger:** a Claude Desktop session asked to *"create this floor plan in Revit … make sure
every dimension is correct … you must recreate it with its dimensions, room tags, etc."*
It succeeded, but the report it produced listed ten problems and the run took far longer than
the task warranted.
**Question:** which of those problems are defects in *paracore*, and what actually closes them?

**Method:** every claim below was re-run against the live installed build (engine
`C:\ProgramData\Autodesk\Revit\Addins\2025\Paracore\CoreScript.Engine.dll`, 2026-10-07 17:28)
with the user's own document (`OneStoreyHouse-Test`, view `00 - Grouond Floor`) open.
Read-only probes only. Nothing in the user's model was changed.

---

## 1. Verdict

**The report's diagnosis was directionally right and factually wrong in three places.** Two of
its items are real engine defects worth fixing; three are the agent's own mistakes, and one
(the room-tag rotation) is a straightforward capability the agent wrongly declared impossible.

The single highest-value gap was **not** in the report's list of engine fixes: the agent had no
way to *see* the drawing it was asked to produce. That is now closed, MCP-side, with no engine
change and no Revit restart — and the before/after is in §4.

| # | Item | Owner | Status |
|---|---|---|---|
| D-MCP-5 | CS0411 `TrackEnumerable<T>` breaks compilation on a cross-call receiver | **PRODUCT** — engine | OPEN (diagnosed, 1-line fix) |
| D-MCP-6 | Compiler line numbers are +2, columns can be off the line | **PRODUCT** — engine | OPEN (diagnosed; MCP mitigation shipped) |
| D-MCP-7 | `export_view` cannot show dimensions or tags | **PRODUCT** — MCP | **FIXED** (verified live) |
| D-MCP-8 | Param-name warning fires on non-parameter strings | **PRODUCT** — MCP | **FIXED** |
| D-MCP-9 | No skill covered dimensions / tags / annotation | **PRODUCT** — MCP | **FIXED** |
| A-1 | *"Revit room tags can't be rotated"* | agent error | corrected in skill |
| A-2 | *"segmented dimensions showed millimetres correctly"* | agent error | corrected in skill |
| A-3 | `NewRooms2` auto-tags → duplicates | agent error | corrected in skill |
| C-1 | The drawing's own wall thicknesses / 35 mm stack | drawing | documented, not a defect |

⚠ **Not a defect:** *"I couldn't see annotations"* is by design of the export, not a bug — but
the **tool** not offering a way to see them was.

---

## 2. D-MCP-5 — the pipeline-tracking rewriter breaks the compile

**Severity: HIGH.** It fails a script that is correct, with a message that names the engine's
own helper. The session lost roughly five calls to it.

### Reproduced, live, 2026-10-08

```
call 1:  var __sb = new StringBuilder();
         __sb.Append("first ");
         Println("declared, len=" + __sb.Length);
         → declared, len=6                                   ✅

call 2:  __sb.Append("second");
         Println("after=" + __sb.ToString());
         → Execution Failed: (3,44): error CS0411: The type arguments for method
           'ExecutionGlobals.TrackEnumerable<T>(IEnumerable<T>)' cannot be inferred
           from the usage. Try specifying the type arguments explicitly.
```

### The causal chain — all five links verified

1. **REPL state DOES persist between calls.** One session id (`mcp-session`) is used for every
   call, and the engine keys its Roslyn `ScriptState` by that id. Proven: `var __pv = 4242;` in
   one call, `Println(__pv + 1)` in the next printed **4243**.
   ⚠ `paracore-gen/.workbuddy-ai/memory/MEMORY.md` says the opposite ("REPL state does NOT
   persist between calls"). **That entry is wrong** and is corrected in this pass.
2. **`SemanticTrackingGuard.ComputeSkipCalls` compiles only the CURRENT submission.**
   A receiver declared in an earlier call is unresolvable in that throwaway compilation.
3. **Its fallback for an unresolved call is to keep the existing behaviour — i.e. to wrap.**
   `SemanticTrackingGuard.cs:79-81`:
   ```csharp
   var method = model.GetSymbolInfo(node).Symbol as IMethodSymbol;
   if (method == null)
       continue;   // unresolved → keep current (wrap) behavior
   ```
4. **`Append` and `Prepend` are in `IntermediateMethods`** (`PipelineTrackingRewriter.cs:49-50`),
   added so that `CurveLoop.Append` / `CurveArray.Append` get tracked. The rewriter matches **by
   name only** — it has no type information.
5. So `__sb.Append("second")` becomes
   `TrackEnumerable(__sb.Append("second"))`, and `TrackEnumerable<T>(IEnumerable<T>)` cannot
   infer `T` from `StringBuilder.Append`. **CS0411.**

### Why it is a defect and not a trade-off

The guard's own docstring says the fallback preserves "the pre-guard behavior". That is true and
it is the wrong choice, because the two failure modes are not symmetric:

| choice for an unresolved call | cost when wrong |
|---|---|
| **wrap** (current) | the script **does not compile** — fatal, and the error names the engine |
| **skip** | one `PipelineDiagnostics` token is missing — cosmetic |

Wrapping is only ever correct when the receiver is an `IEnumerable<T>`; an unresolved receiver is
a coin flip. **The fix is to skip on unresolved.** It also happens to be the behaviour that
matches the observed symptom: `StringBuilder.AppendLine` (not in the set) worked, `.Append` did
not — which is exactly what the session reported.

### The fix

`CoreScript.Engine/Core/Rewriters/SemanticTrackingGuard.cs`, in `ComputeSkipCalls`:

```csharp
var method = model.GetSymbolInfo(node).Symbol as IMethodSymbol;
if (method == null)
{
    // ⚠ Unresolved ⇒ DO NOT WRAP. Wrapping is only valid for an IEnumerable<T>
    // receiver, and an unresolved receiver is a coin flip; getting it wrong
    // fails the COMPILE with an error that names this engine, not the user's
    // code. Losing one pipeline-diagnostic token is the cheaper mistake.
    skip.Add((mapped, name));
    continue;
}
```

⚠ `mapped` must be computed before this branch (`int mapped = node.Span.Start - prefix.Length;`),
so the `mapped >= 0` guard moves up with it.

**Verification gate:** a two-sided standalone probe (see the `paracore-engine-logic-probe` skill)
with the case that MUST be skipped (`StringBuilder.Append` with the receiver unresolved) and the
case that MUST still be wrapped (`GetElements<Wall>().Where(...)` resolved in-submission). A
negative-only suite cannot tell "narrowed" from "deleted".

**Loop cost:** engine rebuild + `install-engine.cmd` **with Revit closed** (the user runs it) +
Revit restart. This is the heaviest loop in the workspace, which is why it is *not* bundled into
this MCP-only pass.

### MCP mitigation — shipped now

`mcp_core/tool_helpers.py` maps CS0411 / `TrackEnumerable` / `cannot be inferred` to an
explanation that names the real cause and three workarounds (use `AppendLine`; build strings with
`+`; declare the receiver in the same submission). It previously fell through to the generic
*"Check paracore://system-prompt"*.

---

## 3. D-MCP-6 — compiler line numbers are +2

**Severity: MEDIUM.** It does not break anything, but it sends the agent to the wrong line, and
the reported column can fall outside the line entirely.

### Measured — five independent failures, all exactly +2

| script length | real failing line | reported line | delta |
|---|---|---|---|
| 2 lines | 1 | 3 | +2 |
| 2 lines | 3 | 5 | +2 |
| 3 lines | 3 | 5 | +2 |
| 4 lines | 4 | 6 | +2 |
| 7 lines | 5 | 7 | +2 |

### Cause

`CoreScript.Engine/Core/ReplSessionManager.cs:126-128` prepends exactly two lines to every REPL
submission and emits **no `#line` directive** to map them back:

```csharp
string fullCode = "using static CoreScript.Engine.Globals.ScriptApi;" + Environment.NewLine +
                  "using Parameter = Autodesk.Revit.DB.Parameter;" + Environment.NewLine +
                  code;
```

The non-REPL path gets this right — `CodeRunner.cs:118` emits `#line hidden`, `ScriptParser.cs:77`
emits `#line N "file"`, and `DiagnosticMapper` maps through `GetMappedLineSpan()`. **The REPL path
is the one that was missed**, and it is the path both MCPs drive.

⚠ The column is unreliable for a *second* reason: the pipeline-tracking rewriter inserts
`TrackEnumerable(` **on the same line**, shifting every column after it to the right. A caret
drawn from a reported column would point at nothing, so the MCP only draws one when the column
still lands inside the line.

### The fix

Engine-side: emit `#line 1 "script"` before the user code in `ReplSessionManager`, and report
diagnostics through `DiagnosticMapper`. Same loop cost as D-MCP-5 — do them in one engine pass.

### MCP mitigation — shipped now

`format_execution_error` now takes the submitted source and prints, for each diagnostic:

```
⚠ Compiler line numbers are the ENGINE's (it prepends 2 lines), so the raw number is +2.
Mapped back to your snippet:
  your line 1:
    1 | __sb.Append("second");
    CS0411: The type arguments for method '…TrackEnumerable<T>(…)'
```

`_ENGINE_PREFIX_LINES = 2` is the **one** place in the MCP that knows the offset, with the engine
file and line named in a comment so the coupling is visible. When the engine fix lands, that
constant goes to `0` and the note is deleted.

⚠ Diagnostics that fall outside the submitted snippet (i.e. inside the engine's injected text)
are labelled as such rather than quoting an unrelated line.

---

## 4. D-MCP-7 — the agent could not see the drawing it was asked to make

**Severity: HIGH for any drawing task.** The session's whole point was dimensions and room tags,
and the one tool that shows the model hid exactly those.

### Measured, on the house model, three exports of the same plan view

| mode | dimensions visible | room tags visible | model fills frame |
|---|---|---|---|
| `model` (was the only option) | ❌ | ❌ | ✅ |
| `all` (`hideAnnotation: false`) | ✅ | ✅ | ❌ ~15% of the frame |
| `tags` (**new**) | ✅ | ✅ | ✅ |

The `all` failure is the engine's own documented trap: Revit does not clip annotation to the
view, so the four section marks beside the plan are rendered too and the export fits *them* to
the page. Measured: the model occupied roughly a seventh of the frame — legible as a thumbnail,
useless for checking a dimension.

### Fix — `annotations: "model" | "tags" | "all"` on `export_view`

`"tags"` is implemented **MCP-side, in the emitted snippet, using raw `Autodesk.Revit.DB`** —
so it needs no engine change, no add-in rebuild and no Revit restart, and it works on the free
add-in and the Pro add-in alike (the `PROJECT_MODELING_PLAN.md` §4 doctrine).

It hides every `CategoryType.Annotation` category **except** an allowlist —
`OST_Dimensions`, `OST_TextNotes`, `OST_RoomTags`, `OST_DoorTags`, `OST_WindowTags` — and rolls
its own `TransactionGroup` back, so the user's view is left exactly as it was. The allowlist
fails safe: an annotation category nobody thought of gets hidden, which can only improve the
framing, never break the drawing.

**Verified live 2026-10-08:** `marker categories hidden: 203`, the export written, and a
follow-up read of the view confirmed `Dimensions / Sections / Room Tags / Text Notes` all
`hidden=False` afterwards. The rollback leaves no undo entry.

⚠ `"tags"` resolves the view itself (to have something to hide categories *on*), so it duplicates
a little of the engine's view-lookup. That duplication is deliberate: the alternative is a
Pro-only dependency or an engine change, both worse.

⚠ If this is ever promoted into the engine it becomes its own **shared** file and syncs cleanly
because nothing was mixed in the first place.

---

## 5. D-MCP-8 — the param-name warning fired on non-parameter strings

**Severity: LOW** (advisory only) but it costs tokens on every reflection-heavy snippet and, more
importantly, **a warning that fires on correct code trains the agent to ignore warnings** — the
same failure class as D-MCP-2.

Measured on the installed build, from two of this session's own probes:

```
Note: "TagOrientation", "TagOrientation", "NewRoom" has no spaces —
Revit parameters use spaces (e.g., 'Fire Rating' not 'FireRating').
```

Those came from `typeof(IndependentTag).GetProperty("TagOrientation")` and
`m.Name.StartsWith("NewRoom")` — three strings, **none of them a parameter name**.

**Fix:** the rule now only inspects the string passed as the **parameter-name argument** of a
Paracore call (`GetStr`, `GetNum`, `WhereParam`, `GroupByParam`, `OrderByParam`, `SetVal`,
`SetParam`, …). A mistyped `.GetStr("FireRating")` is still caught; reflection strings and
`StartsWith` literals are not.

---

## 6. D-MCP-9 — there was no skill for the drawing layer

Twelve skills existed; **none** covered dimensions, tags or annotation. `project-modeling` stops
at geometry, and all three of its verification tiers count *geometry* — so a plan with no
dimensions and untagged rooms passes every check the MCP offers.

That is why the session had to reconstruct `TagOrientation`, the dimension API, the
`NewRooms2` tag behaviour and the room-tag duplication from scratch.

**New skill `annotations-dimensions`**, carrying the measured traps:

- ⚠⚠ **`ValueString` is a display string, not a measurement.** Measured: a 5350 mm dimension
  returns `ValueString = "535"` — the value in the **project's** units (cm), truncated, and it
  **ignores the dimension type's own unit format**. The on-screen text of that same dimension
  reads **5350** (visible in the export). And every **multi-segment** dimension returns `""`.
  Read `d.Value` / `seg.Value` and `.OutputUnit("mm")`.
- ⚠ `Dimension.Value` and `DimensionSegment.Value` are **`double?`** — `.OutputUnit()` on a
  `double?` is CS1929.
- ⚠ `Dimension.Segments` enumerates as **`object`** unless the loop variable is typed
  `DimensionSegment`.
- ⚠ `OutputUnit` returns a **`double`**, not a string (CS0029).
- ⚠ `NewRoom(Level, UV)` = one room, no tag. **`NewRooms2(Level, Phase)` = bulk, and it tags
  them** — which is the duplicate-tag trap the session hit.
- ⚠ **Tag orientation IS settable** (`TagOrientation.Vertical`), and the third enum member is
  **`AnyModelDirection`**, not `Model` as the Revit UI dropdown calls it.
- ⚠ **Room boundaries are stale until the transaction commits** — `IsPointInRoom` and `Room.Area`
  must be read in a *later* call.
- Reflected live: `NewDimension(View, Line, ReferenceArray[, DimensionType])`,
  `NewRoomTag(LinkElementId, UV, ElementId)`, four `TextNote.Create` overloads,
  `NewRoomBoundaryLines(SketchPlane, CurveArray, View)`.

`project-modeling` also gained: the `NewRooms2` trap, the commit-before-read rule, the
**read-only `HandFlipped` / `FacingFlipped`** finding, the door-insert-conflict margin rule, the
fixture bounding-box alignment recipe, the wall-material gap, and pointers to the new skill.

---

## 7. Where the report was wrong — and it matters

| Report claim | Verified reality |
|---|---|
| *"Revit room tags can't be rotated"* | **Wrong.** `IndependentTag.TagOrientation` is read/write (reflection-verified). All five tags are `Horizontal` and could be set `Vertical`. ⚠ The UI says "Model"; the API member is `AnyModelDirection`. |
| *"Segmented dimensions showed millimetres correctly"* | **Wrong.** Every multi-segment dimension returns `ValueString = ""`. Only single-segment returned text, and it was in **project units (cm)**, not mm. |
| *"`Dimension.ValueString` returned cm-rounded text for single-segment dimensions"* | **Right**, and worse than described: it is project-unit text that disagrees with the dimension type and with what the drawing displays. |
| *"`NewRooms2` silently created its own tags"* | **Right.** `NewRooms2(Level, Phase)` is the bulk API and tags what it creates. The skill already said `NewRoom(level, uv)` — the wrong overload was used. |
| *"`export_view` hides annotations by design"* | **Right**, and the engine already had the flag; the **tool** did not expose it. |
| *"I assumed the cook window size"* | **Confirmed.** The model has a 1200 × 1200 mm window, sill 900, that appears nowhere in the drawing. |
| *"`StringBuilder.Append` caused the CS0411"* | **Right cause, wrong mechanism.** Not `StringBuilder` as such — it is *any* call named `Append`/`Prepend`/… whose receiver the guard cannot resolve in the current submission. `AppendLine` is not in the set, which is why that worked. |

⚠ The session also produced one limitation that is **not** a product issue and should not be read
as one: it could not see annotations. It also correctly declined to invent the drawing's missing
data, which is the right behaviour.

---

## 8. The model as built — measured, for the record

Read back from the live document, 2026-10-08:

| | |
|---|---|
| Walls | **9** — 4 × `Exterior - 200mm` (5150, 7435, 5150, 7435 mm) + 5 × `Interior - 150mm Partition` (3175, 3470, 1975, 1975, 500 mm) |
| Overall | 5350 × 7635 mm — consistent with the dimension strings read back |
| Doors | 3 — 900, 850, 800 mm (`HandFlipped=True, Mirrored=True` on two) |
| Windows | 4 — 2 × 1511×1200 sill 900; 1 × 533×600 sill 1500 (bathroom); 1 × 1200×1200 sill 900 (cook, invented) |
| Rooms | 5 — BEDROOM, BATHROOM, COOK, SITTING ROOM, LOBBY; **34.24 m²** total |
| Room tags | 5 — all `Horizontal` |
| Dimensions | 10 — three single-segment (5350, 5350, 7635), seven multi-segment |
| Fixtures | 4 × Plumbing Fixtures |
| Warnings | **0** ✅ |
| **Wall materials** | ⚠ **every wall type reports `layer0mat = UNSET`** |

⚠ **The 0-warning result is real and is worth stating plainly** — the geometry is clean. The
material gap is invisible to `Doc.GetWarnings()`, which is why the Tier 1 check did not catch it:
**a warning count is not a quality measure.** Add a material/function read-back to the Tier 1
recipe.

---

## 9. Still open — for the user to decide

**Engine pass (heaviest loop — `install-engine.cmd`, Revit closed, then a Revit restart):**

1. **D-MCP-5** — skip the wrap when the receiver is unresolved (one branch in
   `SemanticTrackingGuard`).
2. **D-MCP-6** — `#line 1 "script"` in `ReplSessionManager`, diagnostics through
   `DiagnosticMapper`.
3. Optionally promote the `tags` export into a **shared** engine method so the help site, the
   VS Code copilot and `paracore-examples` get it too. ⚠ Class C propagation — 6 doc copies,
   `_api_surface_check.py`.

**MCP-only, cheap, not done (no decision needed to be useful):**

4. `export_view` camera placement (`ViewOrientation3D`) — a named 3D view from an angle.
5. A family catalogue tool — the report asked for it; ⚠ weigh it against *"do not bloat the
   agent"*. It is expressible as a recipe (`GetElements<FamilySymbol>("Doors").Select(...)`), so
   it belongs in a skill, not a ninth tool.
6. A spec-vs-model verifier as a **recipe** (Tier 3 already exists in `project-modeling`); the
   report's "build-and-verify workflow" is that recipe applied to a written spec table.

**The user's model, not touched (all reversible, offered rather than done):**

7. Set the five room tags to `TagOrientation.Vertical` to match the drawing.
8. Assign materials and a wall **function** to the two wall types.
9. Add a floor slab, ceiling and roof; door/window tags; a room schedule.
10. Decide the `AREA=38sqm` note — the rooms sum to 34.24 m² and the footprint is ~40.9 m².

---

## 10. What this pass changed

| File | Change |
|---|---|
| `mcp_core/tools.py` | `export_view` gains `annotations` (`model` / `tags` / `all`); new `_export_view_tags_snippet`; `handle_execution_result` threads the source code |
| `mcp_core/tool_helpers.py` | `_annotate_compile_errors` + `_ENGINE_PREFIX_LINES`; CS0411 suggestion; param-name rule narrowed to parameter-name arguments |
| `mcp_server.py` | `export_view` signature + docstring; `annotations-dimensions` registered |
| `mcp_core/skills/annotations-dimensions/SKILL.md` | **new** — the drawing layer |
| `mcp_core/skills/project-modeling/SKILL.md` | `NewRooms2`, commit-before-read, read-only handing, insert-conflict margin, fixture alignment, wall materials, new traps |
| `mcp_core/skills/display-visualize/SKILL.md` | the three annotation modes |
| `mcp_core/skills/identity-orientation/SKILL.md` | handing is read-only — use `flipHand()` |
| `SKILLS.md` | catalog: 13 skills + the "recreate a plan" usage pattern |

⚠ All of the above are **bundled inside the exe**, so they are invisible to any agent until the
MCP is rebuilt, installed and the client restarted. An edit alone changes nothing.
