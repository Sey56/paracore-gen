# Generalist MCP — Family Editor & Massing Plan

**Status:** proposed, not started
**Date:** 2026-09-30
**Scope owner:** `paracore-gen` (the generalist MCP)
**Verified against:** Revit 2025, live session, 74 families loaded, project (non-family) document

---

## 1. Scope boundary — read this first

This MCP is the **generalist** server. It stays generalist.

| | |
|---|---|
| **IN** | Model querying, parameter read/write, element creation, and now **family & mass authoring** — the things any Revit user does |
| **OUT** | **Watchdogs.** Enterprise/Sentinel concern — `Watchdog()`/`WatchdogReport()` are gated behind `LicenseContext.RequireEnterprise("Sentinels")` in `ScriptApi.cs:331`. Not generalist. Not in this MCP, not in the other one. |
| **OUT** | **Takeoff / BOQ / material sections.** Owned by the `paracore-takeoff` MCP. Do not duplicate, do not cross-reference. |
| **OUT** | Any Pro-tier vertical. Pro features stay in Pro. |

If a capability is ambiguous, it does not go here by default. The failure mode of this
project is sprawl, and the cheapest defence is a hard boundary.

---

## 2. The bet: family and mass authoring

### Why this is the right thing to build

The engine currently has **zero** family or massing support. Verified by grep across
`CoreScript.Engine/` and `Paracore.Addin/` for `FamilyCreate|NewExtrusion|NewRevolution|
EditFamily|NewFamilyDocument|LoftForm|FamilyManager` — no matches.

Meanwhile everything an architect actually draws *is* a family: windows, doors, furniture,
curtain panels, custom profiles, massing. Today the MCP can place an existing family
instance but cannot author one. That is the largest single gap between "query tool" and
"does real work".

### API surface confirmed present in this build

`asm.GetTypes()` on the loaded RevitAPI assembly returns, among 49 matches:

- `FamilyItemFactory` — the creation factory for family documents
- `Form`, `FormArray`, `FormUtils` — conceptual massing
- `FamilyManager`, `Family`, `FamilySymbol`

**Namespace note:** `Autodesk.Revit.Creation` is **not** in the pre-imported list
(`ScriptApi.cs:1-19`). You never need to name it — reach it through the document:
`Doc.Create` (project) and `Doc.FamilyCreate` (family document) return `ItemFactory` and
`FamilyItemFactory` respectively. This matters because the compliance layer hard-blocks any
`Autodesk.Revit.\w+.` literal in submitted code.

### Two sub-capabilities

**A — Loadable family authoring (`.rfa`)**

```
UIApp.Application.NewFamilyDocument(templatePath)   → new family document
Doc.EditFamily(family)                              → edit a loaded family
famDoc.FamilyCreate.NewExtrusion / NewRevolution / NewSweep / NewBlend / NewSweptBlend
famDoc.FamilyCreate.NewReferencePlane / NewReferencePoint / NewModelLine
famDoc.FamilyManager.AddParameter / NewType / Set / AssociateElementParameterToFamilyParameter
famDoc.FamilyCreate.NewDimension(...) → dim.FamilyLabel = familyParameter
famDoc.LoadFamily(Doc, out Family)  |  famDoc.SaveAs(path)
```

**B — Conceptual massing**

Same `FamilyCreate` forms producing `Form` objects, plus `Form.AddProfile`,
`Form.AddEdge`, `Form.AddPath`, `FormUtils.*`, and `FormArray` for arrays along a path.
Adaptive components via `AdaptiveComponentInstanceUtils`.

---

## 3. The speed problem, and the three levers

The user constraint is explicit: **it must really work fast — do not bloat the agent.**

The slowness of family work is not the API. It is (a) boilerplate per round-trip, (b) a
compile per step, (c) transactions per operation, and (d) no way to see the result. Each
has a different fix.

### Lever 1 — one transaction per family, not one per form

Write methods auto-transact. A family with six forms becomes six transactions: six undo
entries, six commits, and — because of `Tx.cs:34-53` — six synchronous appends to
`%APPDATA%\paracore-data\logs\TxDebugLog.txt`.

Wrapping the entire build in a single `Transact("Build family", () => { ... })` fixes all
of it at once. The engine already supports this and skips inner auto-transactions when
`IsModifiable` is true. **Zero engine change — this is a documentation and skill change.**

### Lever 2 — fewer round-trips

The REPL persists variables across calls, so `var famDoc = ...` survives between
`execute_dynamic_query` calls. A build becomes 3 calls (open → build → verify) instead of
10. Additionally, `BuildScript` exists in the proto and is **unused by the MCP** — it
compiles a script to assembly bytes once, so repeated runs skip compilation entirely.

### Lever 3 — the profile/plane prelude (the one real engine addition)

The dominant cost is not the API call, it is the `CurveArray` / `CurveArrArray` /
`SketchPlane` plumbing the agent must emit for every single form. Twenty-five lines of
ceremony per extrusion, re-derived every time, re-compiled every time.

A small set of high-level helpers removes it. **This makes the agent smaller and the
execution faster** — which is exactly the stated requirement. This is not bloat; it is
the opposite of bloat, because it deletes generated code.

Sketch of the surface (to be finalised against the real API in the spike):

```csharp
PlaneXY(z)  PlaneXZ(y)  PlaneYZ(x)  PlaneByNormal(origin, normal)
Profile(params XYZ[])         // closed polygon
ProfileRect(w, h, origin)
ProfileCircle(radius, center)

Extrude(famDoc, plane, profile, end)
Revolve(famDoc, plane, profile, axis, angle)
Sweep(famDoc, path, profile)
Blend(famDoc, plane, bottomProfile, topProfile, height)
```

### Lever 4 — anti-bloat rule (enforce this)

`mcp_server.py:80-122` passes a ~1,200-character `instructions=` string to `FastMCP`.
That string is injected into the model's context on **every single turn**.

**Rule: no family or massing guidance ever goes into that string.** It goes into lazily-read
skill resources, following the existing nine-skill pattern. Anything placed in the
instructions block is paid for on every turn forever, whether relevant or not.

---

## 4. Verification — the part that makes it trustworthy

Building geometry you cannot see is how you ship a plausible wrong answer.

### Tier 1 — numeric, automatic, always on

After any family or mass build, report — without the agent having to remember:

- solid count
- total volume (`Solid.Volume`)
- bounding-box extents
- `famDoc.GetWarnings()`

A revolve that produced zero volume, or an extrusion 0.003 m tall where 3 m was intended,
is caught here instantly and cheaply. This tier should be wired in, not prompted for.

### Tier 2 — visual, on demand

Export a 3D view to PNG via `ImageExportOptions` / `View.ExportImage` and let the
multimodal agent look at the result. The engine already pre-imports
`SixLabors.ImageSharp` (`ScriptApi.cs:11-13`), so image handling is available engine-side.

**This is the only place computer use belongs in this plan** — as a camera, not a hand.
Preferred over screen-scraping because it is deterministic, resolution-controlled, and
does not require Revit to be the foreground window. Reserve real screen capture for dialogs
that API image export cannot see.

---

## 5. Work plan, split by build loop

The organising principle is **which build loop the work touches**, because that is what
governs how fast you can iterate. A Revit add-in change costs a build → close Revit → UAC →
reopen cycle. MCP-only work costs nothing.

### Track A — MCP only (Python + Markdown). No add-in rebuild, no Revit restart.

| # | Item | Notes |
|---|---|---|
| A1 | **Fix `ping`** | Confirmed defect, see §7 D-MCP-1. Call `GetStatus`; report `revit_open` and `paracore_connected` separately. |
| A2 | **Retry-storm protection** | See §6.1. Dedup, heartbeat, "do not retry" signal, queue bound. Urgent — prevents a deadlock that needs a Revit restart. |
| A3 | **`get_context` tool** | Wraps the `GetContext` RPC. Active view + type/scale/detail level, selection, levels with elevations, project info, workshared state. Auto-call at session start. Autodesk ships an equivalent (`get_active_context`) — we ship nothing. |
| A4 | **`pick_object` tool** | Wraps the `PickObject` RPC. The engine already has `Pick()` (`ScriptApi.cs:64`) but it needs its own tool so it is not run inside a transaction and can carry its own timeout. |
| A5 | **Two skill resources** | `family-authoring` and `massing-forms`, in the existing `mcp_core/skills/` pattern. Subject to the Lever 4 rule. |
| A6 | **Enforce Lever 1 in the skills** | Document the single-`Transact`-per-build pattern as the default. |
| A7 | **Narrow `_ANTI_PATTERNS` to a lint** | See §6.4. Keep the warnings, stop treating the regex layer as the security boundary. Fixes D-MCP-2. |

**Track A status: COMPLETE (2026-09-30).** Implemented and verified short of a live run:

| # | Status | Where |
|---|---|---|
| A1 | Done | `grpc_client.probe_connection()` + `is_revit_running()`; `tools.ping()` |
| A2 | Done | `tools.single_flight()` / `RevitBusy` / `busy_message()`; bounded `pick_object` timeout; "retry ONCE, never identically" in the tool docstrings; the harmful "Try again" removed from the `DEADLINE_EXCEEDED` branch |
| A3 | Done | `tools.get_context_report()`; `get_context` tool |
| A4 | Done | `tools.pick_object_report()`; `pick_object` tool |
| A5 | Done | `mcp_core/skills/family-authoring/SKILL.md` (12.3 KB), `massing-forms/SKILL.md` (10.1 KB); catalogued in `SKILLS.md` |
| A6 | Done | "ONE transaction per build" is the first structural rule in both new skills |
| A7 | Done | `_HARD_ERRORS` / `_LINT_RULES` split; `lint_paracore_conventions()` wired into both tool paths |

Also fixed while in there: **D-MCP-3** (stale output limits in three docstrings) and **D-MCP-5**
(the watchdog section in the bundled extension reference).

**Verification actually performed** (all against the live Revit 2025 API, read-only):
11/11 skills resolve through `mcp_server`'s own loader; the D-MCP-2 regression snippet passes
the blocking check and raises a lint; four genuine hard errors still block; the
`refused_busy` / `lint_notes` metric kwargs no longer raise. Full API surface for
`FamilyItemFactory` (30), `FamilyManager` (40), `Form` (47), `FormUtils` (3), `FormArray` (10),
`Document`/`Application` family plumbing, the profile/sketch-plane types and the template
paths was read off the running API rather than recalled.

**Not yet verified:** anything that writes. `NewFamilyDocument` → build → `LoadFamily` remains
untested end to end — that is still the B1 spike, and it is still the thing that decides
whether the plan holds.

### Track B — engine (C#). Add-in rebuild + Revit restart.

| # | Item | Notes |
|---|---|---|
| B1 | **Spike: prove the loop on one form type** | ✅ **Phase 1 PASSED 2026-09-30** — create → build → verify → save → close, **732 ms**, on the live API from the REPL context. `LoadFamily` (Phase 2) still to do. See the result block below and §8. |
| B2 | **Profile/plane prelude** | The helpers in Lever 3, once the spike has settled the shapes. |
| B3 | **`preview` execution mode** | Run inside a transaction, capture a structured diff (created / modified old→new / deleted), `RollBack()`, report. Needs a deliberate rollback path — `Tx.cs` currently only rolls back on exception. Caveat to surface honestly: exports to disk and family loads are **not** rollbackable and must be reported as explicit non-rollbackable side effects. |
| B4 | **Investigate per-call logging** | `Tx.cs:12,30,37,40,42,45,49` appends synchronously to `TxDebugLog.txt` on every transaction. `PrintCallbackDebug.txt` is at 4 MB and was written again during this session. Both are directly opposed to "must work fast". |

#### B1 result — Phase 1, measured 2026-09-30

Script: `spikes/b1_family_spike_phase1.cs`. Live Revit 2025, project
`B+G+2 - KedirMohammed - Residential`, **project left unchanged** (doc count 1 → 1).

| step | result | time |
|:---|:---|---:|
| `Application.NewFamilyDocument(Metric Generic Model.rft)` | OK, `IsFamilyDocument=True` | 414 ms |
| `FamilyCreate.NewExtrusion(true, profile, sketchPlane, 3000mm)` | OK, `commit=Committed` | 137 ms |
| bbox verification | **600 × 400 × 3000 mm — exact** | — |
| `famDoc.SaveAs(%TEMP%\\b1_phase1_full.rfa)` | OK, 466,944 bytes | 411 ms |
| `famDoc.Close(false)` | OK, docs back to 1 | ~100 ms |
| **total** | | **732 ms** |

**Three findings, all now fixed in the skills:**

1. ⚠⚠ **`Transact()` cannot target a family document.** `ExecutionGlobals.Transact` always calls
   `Tx.Transact(Doc, …)`, so the `Action<Document>` overload hands you the **project**. The first
   spike attempt used it, called `d.FamilyCreate` on the project, and **stalled the REPL for the
   full 120 s deadline** instead of failing cleanly. Use `new Transaction(famDoc, "…")` directly —
   `Autodesk.Revit.DB` is pre-imported. **This was documented wrong in both new skills and is fixed.**
2. **`NewExtrusion` returns `Extrusion`, whose base is `GenericForm` — not `Form`.** Declaring
   `Form f = …` fails to compile (`CS0029`). The massing creators (`NewLoftForm` etc.) *do* return `Form`.
3. The **create / build / save / close loop is cheap** (~1 s). The 120 s was never Revit; it was ours.

**Still open in B1:** Phase 2 — `LoadFamily` back into the host project, and the `EditFamily`
round-trip cost (unknowns 2 and 4 below).

### Track C — verification

| # | Item | Notes |
|---|---|---|
| C1 | Automatic numeric verification on write results (§4 Tier 1) | Depends on B1. |
| C2 | Image export + visual check (§4 Tier 2) | Depends on B1. |

### Track D — later, generalist but not now

Genuinely generalist, deliberately deferred so it does not compete with family work:
dimensions, tags, sheets/viewports, schedules, export. Revisit only after Track B1–B2 lands.

### Recommended sequence

1. **A1–A5** — one afternoon, no rebuild, immediate value. Fixes a confirmed defect and
   gives the agent context it currently lacks.
2. **B1 spike** — prove family creation works at all from the MCP context before committing
   to B2. If the spike fails, the whole plan changes shape and we find out cheaply.
3. **B2**, then **C1**, then **B3**.
4. **C2**, then **D**.

---

## 6. Revisions from the landscape research (2026-09-30)

Full findings in [`REVIT_MCP_LANDSCAPE.md`](REVIT_MCP_LANDSCAPE.md). Four changes to the plan
above, in priority order.

### 6.1 Retry-storm protection moves to the front of Track A (urgent, cheap)

Axoworks documented that Autodesk's own server **deadlocks permanently** when an async agent
retries failing calls — *"only a full restart clears it"* — and identified the trigger as a
client that *"assumes failure after ~30s and initiates rapid-fire retries."*

Revit's API is single-threaded. Our tool descriptions currently say *"Self-correct up to 3
times"* and our REPL deadline is 120 s. **That is the documented failure shape.** Worse, our
`ping` lies (D-MCP-1), so an agent cannot tell a busy Revit from a dead one — it just retries.

Add, all Python-side and cheap:
- **Request deduplication** — coalesce duplicate in-flight calls.
- **Heartbeat** — as a task nears the deadline, return *"Revit is busy. Do not retry."*
- **A queue bound** so a retry loop cannot grow unboundedly.

This is worth more than any feature, because it prevents a failure that requires restarting
Revit.

### 6.2 Preview becomes the full verified-write contract

Horizun's shape is stronger than what §5/B3 proposed. Adopt all of it:

**rehearse → apply → re-read**, with:
- `dry_run` as the *default* for risky operations, and genuinely side-effect-free (they shipped
  a bug where a dry run still wrote — treat "dry run wrote something" as a P0 class).
- **Post-commit re-read** — re-read each requested value and report requested vs actual.
- **Undo of the last verified batch, refusing when the model or file changed since.** The
  refusal is the point.

### 6.3 New track — reusable procedures

Everyone else accumulates operations; we regenerate code every time.

- mcp-servers-for-revit: `search_modules` / `use_module` — a library of pre-tested modules.
- Horizun: `promote_script` — *"so it stops being ad-hoc code."*

Proposed: `search_procedures` / `run_procedure` / `promote_procedure`, backed by the existing
skill-file mechanism. Loaded on demand, so it costs no context. **This is the strongest answer
to "must work fast" that also reduces bloat** — the second time a family is built, the agent
runs a procedure instead of writing code.

**Implemented 2026-10-02, family-scoped — see
[`FAMILY_ARTIFACT_WORKFLOW.md`](FAMILY_ARTIFACT_WORKFLOW.md).** The narrow slice of this track
is now in force with **no MCP change**: a family's build script lives in
`Documents\ParacoreFamilies\<FamilyName>\build.cs` and is the source of truth, with a generated
`manifest.json` beside it so revisions are diffable and a `CHANGELOG.md` quoting each defect
report. That establishes the shape this track would generalise — if it is built, those
directories are its first entries.

### 6.4 Replace the regex blocklist with permission profiles

Horizun filters the *tool set* by profile (`safe_write` 70 / `full_write` 79 / `unsafe_code` 80
/ `core` 4) rather than scanning submitted code. Stronger, and quieter — it removes D-MCP-2 as
a side effect. Our `_ANTI_PATTERNS` regex layer should become a *lint* (helpful warnings), not
the security boundary.

### 6.5 Two small additions

- **Coordinate origin awareness.** Axotopia built a translation layer explicitly *"to prevent
  LLM hallucination"* — Global Z (Internal Origin) vs Project Z (Project Base Point).
  `InputUnit()` handles units but says nothing about origin. A project with a non-zero base
  point will silently produce confidently-wrong placements.
- **Session cleanup.** mcp-servers-for-revit ships `reset_model` to clear AI-created
  intermediate state. An agent that creates things needs a way to find and remove what it made.

### 6.6 What the research confirms we should not change

- **The fluent DSL stays.** Nearly every competitor sends raw C#/Python. The Grasshopper work
  recommends a DSL as an intermediate language precisely to fight translation loss and
  accumulated error — we already are one. This is the strongest differentiator we have.
- **Five tools stays.** `puran-water` (8 tools) and `multiCAD` (7 tools → 56 commands) confirm
  consolidation beats sprawl.
- **Progressive disclosure stays.** Horizun cut `tools/list` by ~64 KB without dropping a single
  tool; the Grasshopper work independently built "tool scope control" to stop the LLM's
  attention scattering. Both arrived at our existing pattern.
- **No GUI-driving modelling.** No Revit MCP in the field does it, and every capable server —
  including Autodesk's own — uses the API. ⚠⚠ **CORRECTED 2026-10-02:** this was originally
  justified by hungpixi's threading note (direct writes from a non-UI thread crash; everything
  marshals through `ExternalEvent`). **That was a non-sequitur.** `ExternalEvent` constrains
  calling the **Revit API** off Revit's UI thread; GUI automation never calls the API — it
  injects OS input (`SendInput` / UIA) that arrives through Revit's own message loop, already on
  the UI thread. **GUI-driving Revit is possible and demonstrated**; it is the wrong tool for
  *reliability and precision* reasons, not a threading one. See `REVIT_MCP_LANDSCAPE.md` §5 and
  `REVIT_COMPUTER_USE_RESEARCH.md`. Computer use stays a camera.

---

## 7. Defects found during this investigation

### D-MCP-1 — `ping` reports success without checking anything (CONFIRMED, reproduced)

`mcp_server.py:147-156`:

```python
@mcp.tool()
def ping() -> str:
    _SESSION.record_ping()
    return "pong — Paracore MCP server connected to Revit. Read paracore://skills next..."
```

No gRPC call is made. `get_status()` exists at `grpc_client.py:112-128` and is called by
nothing — the import at `mcp_server.py:31` pulls in only `close_channel` and `init_channel`.

**Reproduced:** with Revit closed and the Paracore server off, `ping` returned
*"pong — Paracore MCP server connected to Revit."*

**Impact:** every session begins with a false assurance. The agent's first instruction is
to call `ping`; it is told the connection is good when there is no connection. All other
tool descriptions also instruct the agent to trust `ping`.

**Fix:** call `get_status()` and report `revit_open` and `paracore_connected` separately.
Note `GetStatusResponse` has both fields, so "Revit is open but the server is off" is
distinguishable — which is precisely the case the user wants reported correctly.

**Status: FIXED (2026-09-30, Track A).** Implemented as `probe_connection()` +
`is_revit_running()` in `grpc_client.py`, consumed by `ping()` in `mcp_core/tools.py`.
`ping` now distinguishes four states: connected / server-up-but-no-document / **Revit running
but the server toggled off** / Revit not running. gRPC alone cannot separate the last two —
both close port 50051 — so a `tasklist` process check supplies the missing signal. The
cheat sheet is now returned *only* on a genuine connection.

*Pending the user's toggle-off observation, which is the acceptance test.*

### D-MCP-2 — compliance layer false-positives on non-element LINQ (FIXED)

`_ANTI_PATTERNS` (`tool_helpers.py:83-86`) blocks `.OrderBy(\w+ =>` and rewrites it to
`.OrderByParam("Name")`. That advice is correct for element collections, but
`.OrderByParam` does not exist on `List<string>`. Any plain-list sort is rejected with
advice that cannot be followed.

**Reproduced:** `asm.GetTypes().Select(t => t.Name).OrderBy(n => n)` was blocked during
this session's recon.

**Impact:** low for end users, real for any agent doing reflection or non-element work.

**Status: FIXED (2026-09-30, Track A).** The flat `_ANTI_PATTERNS` list was split into
`_HARD_ERRORS` (7 rules, blocking — only constructs that genuinely cannot run) and
`_LINT_RULES` (advisory — attached to the output, never blocks). `check_paracore_compliance()`
is now narrow and blocking; `lint_paracore_conventions()` is advisory and wired into both
tool paths. Capability boundaries belong at the permission layer, not in regexes over source
text. Regression-tested: the exact snippet above now passes the blocking check and raises a
lint note instead.

### D-MCP-3 — tool docstrings understated the output limits (FIXED)

`_explore_revit_data` and `_execute_dynamic_query` both documented "first 5 rows + total,
first 10 lines". The summarizer's actual constants are `MAX_TABLE_ROWS = 50`,
`TABLE_TAIL_ROWS = 2`, `MAX_TEXT_LINES = 20`, `SHOW_ALL_TABLE_THRESHOLD = 50`. The agent was
under-told by a factor of five and would over-narrow queries or over-paginate.

**Reproduced:** a 24-row table rendered in full, contradicting the documented "first 5 rows".

**Status: FIXED (2026-09-30, Track A)** in `mcp_server.py` and in the shared
`mcp_core/tools.py` docstrings.

### D-MCP-4 — `sanitize_csharp_code()` output is computed and thrown away (OPEN)

`validate_csharp()` sanitizes the code and then runs the checks against the sanitized copy —
but the callers pass the **original** `csharp_code` to `execute_repl()`:

```python
def validate_csharp(csharp_code: str) -> str | None:
    code = sanitize_csharp_code(csharp_code)   # sanitized...
    compliance = check_paracore_compliance(code)   # ...only used for checking
    ...
    return None

# caller
error = validate_csharp(csharp_code)
...
result = execute_repl(csharp_code, ...)        # original, unsanitized
```

The sanitizer's own docstring says it "runs automatically before every execution so the agent
can't get it wrong". It runs before every *check*, not every *execution*. An agent that writes
`.GroupByParam("Level [String]")` still sends that literal to Revit and gets a runtime failure.

**Impact:** real but bounded — only fires when the agent appends a `[Type]` suffix, which the
`_read_extension_methods` docstring explicitly warns against. Every other session is unaffected.

**Not fixed deliberately.** The fix is one line, but it changes *what code runs in Revit*, and
the sanitizer's regex also rewrites `"Name (Text)"`-shaped strings — a legitimate parameter
name in that shape would be silently mangled. That trade deserves an explicit decision rather
than a silent change. Recorded here as OPEN.

### D-MCP-5 — Enterprise-gated watchdog API advertised through the extension reference (FIXED in the shipped copy)

`EXTENSION_METHODS.md` carried a `### Watchdogs (background idle-time callbacks)` section
documenting `Watchdog()` and `WatchdogReport()`. That file is bundled by the installer
(`paracore-gen.spec:4`) and served as `paracore://extension-methods`, so the generalist MCP was
advertising an API gated behind `LicenseContext.RequireEnterprise("Sentinels")`.

**Not** in the always-injected prompt — `build_prompt()` composes only from
`mcp_core/prompts/*.md`, which is clean (verified by grep). The exposure was via the resource
and the `_read_extension_methods` tool.

**Status: FIXED (2026-09-30)** in `paracore-gen/EXTENSION_METHODS.md` — the section is removed
and the file re-verified clean. **Still present** in the sibling canonical copy at
`paracore/EXTENSION_METHODS.md` (the public free repo), which `prompt_assembler._read_shared()`
prefers in dev mode. That copy is a different repository and a public doc, so it was left for
the user to decide.

### D-MCP-6 — the `doc.` / `document.` HARD errors match the English word (FIXED)

`_HARD_ERRORS` carried `(?<![.\w])doc\.` and `(?<![.\w])document\.` — no trailing guard. Both
therefore match the ordinary **English word at the end of a sentence**, so any comment or string
reading *"…the active document."* was **BLOCKED**.

**Reproduced 2026-10-02**, writing `mcp_core/skills/family-authoring/build-template.cs`: the
template was rejected on exactly two comments — `THROW on a project document.` and `always reads
the ACTIVE document. In family work…`. Both are correct, useful comments about correct code.

**Impact: high, and worse than a lint.** This is the *blocking* layer, so the cost is a
round-trip that cannot be worked around by ignoring advice — the agent must guess which innocent
word tripped it, with no indication that the trigger is prose rather than code. It is the same
failure class as D-MCP-2, but on the tier where it does damage.

**Fix:** added `(?=\w)` — a real member access (`document.SaveAs`, `doc.Delete`) still matches,
prose does not. Regression-guarded in both directions by
`spikes/verify_lint_narrowing.py`.

⚠ **The compliance layer scans COMMENTS**, not just code. Worth knowing when writing any
documented script.

### D-MCP-7 — two lints fire on correct family-authoring code (FIXED)

Both `_LINT_RULES` entries below matched constructs that family authoring **requires**:

| rule | why it cannot be followed |
|---|---|
| `new FilteredElementCollector\(` | `GetElements<T>()` has **no document overload** — it always reads the ACTIVE document. Family work operates on a SECOND document (`NewFamilyDocument` / `EditFamily`), where the collector is the only option. |
| `\.get_Parameter\(` | `get_Parameter(BuiltInParameter.X)` returns the **`Parameter` object**, which `GetStr`/`GetNum` cannot supply — and which family work needs for `GetAssociatedFamilyParameter` and `AssociateElementParameterToFamilyParameter`. |

**Reproduced 2026-10-02** against `build-template.cs`: both fired, on the two lines that are the
whole point of the template.

**Impact:** moderate on its own, corrosive in aggregate — a lint that fires on correct code
teaches the agent that lints are noise, which is precisely the habit the layer exists to prevent.

**Fix:** narrowed both. The collector rule now matches only the active-document form
(`(Doc)` or no argument); the `get_Parameter` rule now matches only the **by-name** form
(`get_Parameter("Name")`). Both remain advisory. Regression-guarded by the same probe.

**Status: D-MCP-6 and D-MCP-7 FIXED (2026-10-02)** in `mcp_core/tool_helpers.py`.
⚠ Both are **bundled** (`paracore-gen.spec:4`) → they do not reach the *running* MCP until the
server is rebuilt and reinstalled.

---

## 8. Open unknowns — resolve in the B1 spike, do not assume

1. ✅ **ANSWERED 2026-09-30 — YES, it works.** `Application.NewFamilyDocument(templatePath)`
   returns a valid family document from the MCP's REPL context in **414 ms**
   (`IsFamilyDocument=True`), and it can be built in, saved and closed from the same script.
   The UI-thread concern was real but the answer is positive. **Caveat:** the transaction must be
   a direct `new Transaction(famDoc, …)` — `Transact()` silently targets the project (see §5, B1).
2. **Does `LoadFamily` back into the host project succeed from that context?** Same
   concern, and it can fail if the family is open elsewhere. **Still open — this is Phase 2.**
3. **Is in-place mass creation still available in Revit 2025 projects?** The massing
   commands have moved around across recent releases. Do not assume — check. **Still open.**
4. **What is the real cost of `EditFamily` → modify → `LoadFamily`?** If the round-trip is
   slow, the whole family workflow needs a different shape (build in a new family doc, save
   to disk, load once). **Still open**, but the build half is now known to be cheap:
   create + build + save + close = **732 ms total**, so the round-trip cost lives in
   `EditFamily`/`LoadFamily`, not in authoring.

These four answers determine whether Track B2 is worth building as designed. The spike
exists to answer them for the price of an afternoon.

**Partially answered by reflection (2026-09-30, no writes).** The *shape* of the API is now
known rather than assumed — the signatures, the argument types, the template paths, and the
fact that `Doc.FamilyCreate` / `Doc.FamilyManager` throw rather than return null on a project
document. What reflection cannot answer is whether any of it *runs* from this context. All
four unknowns above are behavioural and remain open.

One structural surprise worth carrying into the spike: **the conceptual-massing form creators
live on `FamilyItemFactory`** — `NewLoftForm`, `NewExtrusionForm`, `NewRevolveForms`,
`NewSweptBlendForm`, `NewFormByCap`, `NewFormByThickenSingleSurface` are all on
`Doc.FamilyCreate`, not on `Doc.Create`. So massing is not a separate API; it is family
authoring against a mass template. That means **B1's spike covers massing too** — one
`NewExtrusion` in a family document proves the whole family of creators, and the
`NewFamilyDocument` question becomes the single highest-value thing to test.

Also worth noting for the spike: the form creators take `Reference` / `ReferenceArray` /
`ReferenceArrayArray`, while `NewExtrusion` / `NewBlend` take `CurveArray` / `CurveArrArray`.
Turning freshly-created reference points and curves into those `Reference`s is the one hop
that is documented in the skills as explicitly unverified.

---

## 9. What this plan deliberately does not do

- It does not add a large number of new MCP tools. Five tools over one strong primitive
  beats thirty tools, and tool sprawl is the stated reason this project feels unmanageable.
- It does not put anything in the always-injected `instructions=` block.
- It does not touch watchdogs, takeoff, or any Pro vertical.
- It does not drive the Revit GUI to model. The API is faster, exact, and in-process; the
  GUI is a client of that same API and gives up the in-process advantage for nothing.
