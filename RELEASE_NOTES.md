## Paracore-Gen v2.1.0

Full notes: [Release-Notes-2.1.0.md](Release-Notes-2.1.0.md) · Previous: [v2.0.0](https://github.com/Sey56/paracore-gen/releases/tag/v2.0.0)

### Built on the shared core

- **8,393 lines lighter** — the eight REPL tools, ten prompt sections, nine skills, the domain registry and the gRPC client are now imported from `paracore/mcp/` instead of carried as a copy
- **The drift is gone** — the five copies had already diverged; there is one text now

### Tools

- **`export_view`** takes optional `execution_mode` (default `read_write`) and `license_tier`, so a read-only caller can declare its own posture
- **`pick_object` removed** from this server's surface (round 4) — it is a gallery/`Params` concern; the REPL path uses `Selection` or element ids. The other seven REPL tools are unchanged, and `pick_object` stays registered for the servers that do want it

### Plumbing

- The three REPL IntelliSense client calls (completion, diagnostics, hover) are in `grpc_client.py`
- `VERSION` is bundled from the build CLI, not the `.spec`; proto stubs regenerated from `protos/corescript.proto`

### From the pre-release review

- **Quantities are no longer rounded before they are used** — `GetNum(name, unit)` returns the exact conversion; rounding moved to `FormatUnit` / `GetVal`. ⚠ Takeoff numbers will shift in the last decimals, in the accurate direction
- **Agent loops can be interrupted** — the REPL path never applied `TimeoutRewriter`, so `CheckTimeout()` was never called; it now runs with a 90 s budget per submission
- **`explore_revit_data` is read-only for real** — the snippet runs inside a `TransactionGroup` that is always rolled back, so even the reflection bypass is discarded by Revit
- **The schema stopped printing parameter names that cannot resolve** (`Level [Reference]`)
- **The system prompt no longer calls nine advisory patterns "REJECTED"** — split into REJECTED vs AVOID, matching `ping`
- Also: a no-op transaction no longer reports "UNVERIFIED capture"; `WhereMatches` advice corrected; known-views list shows the view type and dedupes
- **Writes now tell the agent to read first** — `ping` and the system prompt require reporting old → new before an overwrite, because the review lost wall Marks and an offset to unrecorded writes
- **`%TEMP%\paracore_views` no longer grows forever** — exports older than 7 days are pruned on the next export
- **Second review pass** — a script's last line is no longer truncated away (text keeps first 12 + last 8 lines); an existing-but-empty parameter is no longer reported as a misspelling; the reflection *entry points* are refused, which closes the split-string bypass on file/network/process; lambdas get the timeout check and `Thread.Sleep` is refused
- **Third review pass — two silent wrong writes closed.** An unrecognised unit used to mean "already in feet", so `SetNum("Base Offset", 5, "furlongs")` committed 5 feet; it now throws and lists what is supported. `SetVal` by name now searches only the categories that parameter can hold, refuses an ambiguous name with its candidates, and treats `"None"` / `"<None>"` / `"Unconnected"` / `"-1"` as "clear" instead of hunting for a same-named element — which is how it once wrote a Phase into a wall's Top Constraint. `WhereMatches` now sees family names, so `WhereMatches("Basic")` finds "Basic Wall". Also: `FormatUnit` renders `m²`/`m³`, the group-filter example was a call that did not compile (CS1501), `read_extension_methods()` no longer cuts mid-snippet, and `create-geometry` stops pointing at skills this server does not have
- **The skill set now matches what this server is for — and the dead prompt system is gone.** `paracore-model` is what models; gen generates REPL on the fly against the raw Revit API, LINQ and the DSL. So `create-geometry` is filtered out of gen's catalogue (eight method skills, not nine) and stays in the shared core for the servers that model. That exposed the cause of a week of confusing reviews: **nothing was deleted when the implementation changed.** `build_prompt()` assembled ten `prompts/*.md` into a 36 K system prompt and had had NO caller since the core moved — yet it, its ten-file list and its files stayed on disk and shipped in every installer. Eight of the ten had no reader; they are deleted, along with `build_prompt()`, `SKILLS.md` (a generated doc that could not see the Domain's filter) and family's three dead prompt overrides. Two things were rescued first: `verification.md`'s verify/retry rules, now a block in `COMMON_RULES`, and `globals.md`'s `Doc.ProjectInformation` / `Doc.PathName` / `Doc.IsWorkshared`, which existed only behind a resource nobody reads — `get_globals` is a tool now
- Full notes, including what could not be reproduced and what still needs a live run: [Release-Notes-2.1.0.md](Release-Notes-2.1.0.md)
- **Fourth review pass — schema tables are no longer truncated.** The 50-row table cap was cutting `CombinedParams()` / `InstanceParams()` / `TypeParams()` results in half, making real parameters look missing. A `cap_exempt` flag on the wire (proto field 4) tells the summarizer to show the table whole; a `SchemaRows` marker in the engine identifies schema output. Element dumps still cap. Also: `pick_object` dropped from gen's surface (gallery concern, not REPL); `ping` cheat-sheet documents which tables are never cut vs capped
- **Fifth review pass — the schema example named a parameter that does not exist.** `search_schema`'s runnable example was a fixed template using `e.GetStr("Level")`; **Walls have no `Level`** (62 parameters, nearest is `Base Constraint`), and `GetStr` on a missing name returns `""` with no error — so the advice compiled, ran, and produced a blank column, printed two lines under the list that disproves it. The example is now derived from the rows above it (and picks a unit that matches the parameter). Also: float noise gone (`3.0000000000000004` → `3`, totals included), dead `paracore-model` / `paracore-family` pointers removed from `create-geometry` **and from the live system prompt** — the same pointer survived in `GEN_INTRO`, the block delivered on every session, where no gate looked; there is now a gate on the delivered string, `paracore://system-prompt` pointers replaced by the `_read_extension_methods` tool (resources are never read by Claude Desktop) and four messages that named a non-existent tool corrected, and private working notes (`Birr`, "house model", dated measurements, Pro-tier references) removed from the skills and the method reference. ⚠ Two of the review's seven findings were already fixed in source — it had been run against the previous build

### Requirements

- **Paracore Add-in v4.8.1** — released together
- ⚠ The consent-gate fix needs both halves: Gen 2.1.0 against add-in 4.8.0 still auto-approves the dialog, because 4.8.0's offers `OK`
