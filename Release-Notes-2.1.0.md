# Paracore-Gen v2.1.0

The generalist Revit MCP server, now built on the **shared MCP core**. Standalone installer; not
bundled with the add-in. Ships with **Paracore Add-in v4.8.1**.

## Highlights

- **8,393 lines lighter.** The eight REPL tools, the ten system-prompt sections, the nine shared
  method skills, the domain/skill registry and the gRPC client used to be a *copy* in this repo.
  They now live once, in `paracore/mcp/`, and this server imports them. One fix reaches all five
  MCPs — the same shape as the generic engine itself.

- **The drift is gone.** The copies had already diverged: this one read *"How many per type?"*
  where `model` and `gen` read *"per level"*. There is one text now, and a fix to it lands
  everywhere at once.

- **`export_view` can declare the caller's own posture.** It takes optional `execution_mode`
  (default `read_write`) and `license_tier`, so a caller that runs read-only can say
  `execution_mode="read_only"` instead of claiming a posture it does not have. This tool genuinely
  is safe under it — the read-only flag only gates the script-facing `Transact`, which `export_view`
  never touches.

- **The REPL IntelliSense client calls.** `grpc_client.py` gains the three RPCs behind completion,
  diagnostics and hover — the client half of the add-in's Roslyn workspace. This is plumbing for
  tools that want it, not a new tool.

- **`VERSION` is bundled into the exe from the build CLI**, not from the `.spec`. The spec is
  regenerated on every build, so a version written into it was one build away from being stale.

- **Proto stubs regenerated** from `protos/corescript.proto`, the single wire authority.

## No tool was added or removed in the core set

The eight REPL tools are unchanged, and `export_view`'s two new parameters are optional — an
existing client keeps working untouched. ⚠ `pick_object` was removed from this server's tool
surface in round 4 (see below); it remains registered for servers that need it.

## From the pre-release review

An external review ran about 30 calls against a test model before this release. Every item
below was reproduced before it was changed, and the one that could not be reproduced is listed
as such rather than quietly dropped.

### Corrected

- **Numbers were rounded before they were used.** `GetNum(name, unit)` and `OutputUnit(unit)`
  rounded to 2 dp *in the value*, so a 5.065 m wall read 5.07, a 915 mm door read 0.91 m, and
  summing wall areas gave 95.23 m² against 95.2417 exact on a nine-wall model. Both now return
  the **exact** conversion; `FormatUnit`, `FormatValueOnly`, `GetVal` and `GetStr(unit)` do the
  rounding — half away from zero, not .NET's banker's rounding.
  ⚠ **This moves takeoff quantities.** They become right, and they will differ from the previous
  release in the last decimals. That is the point.

- **A loop in agent code could not be interrupted.** `TimeoutRewriter` injects `CheckTimeout()`
  into every loop body, and the compiled-tool path applied it — the REPL path, which every MCP
  snippet uses, never did. Measured live: a 25 s loop returned normally, while calling
  `CheckTimeout()` by hand threw at 1 s. The mechanism worked; only the injection was missing.
  The REPL path now applies it with a **90 s** budget per submission (under the 120 s gRPC
  deadline), re-armed on every call so one script's `SetExecutionTimeout` cannot leak into the
  next.

- **`explore_revit_data`'s "read-only" is enforced now, not merely scanned.** The snippet runs
  inside a `TransactionGroup` that is always rolled back, so a model write reached by any route
  — including the reflection bypass the review demonstrated — is discarded by Revit itself. The
  pattern scan stays in front of it for a clear message; it is no longer the only layer.

- **The schema printed parameter names that do not exist.** Two parameters sharing a name were
  disambiguated by appending the storage type — `Level [Reference]`, `Frame Material [String]` —
  while the list told the caller to copy the name verbatim. `GetStr("Level [Reference]")`
  returns empty and warns. The real name is emitted now, identical rows are collapsed, and the
  MCP strips a leftover annotation so an older add-in still behaves.

- **A no-op transaction claimed its measurement had failed.** `Tx` warned "the capture is not
  working … UNVERIFIED" whenever no change event arrived — including a committed transaction
  that changed nothing, which cannot raise an event. Now guarded on `TotalChanged > 0`, the
  same guard `Batch` already had.

- **The `WhereMatches` advice was wrong.** It searches the element and family **name**, never a
  parameter, and the error-suggestion text was sending callers to it for parameter values. That
  text now points at `WhereParam("Name", "contains", text)`, which already existed.

- **The system prompt still claimed ten patterns "will be REJECTED"** when nine of them run
  with an advisory note attached. Split into REJECTED (blocking) and AVOID (advisory), matching
  what `ping` has said since the last build.

- **Known-views errors listed the same name twice.** Revit allows two views to share a name
  across view types — "Level 1" as both a FloorPlan and a CeilingPlan on the test model. The
  list shows the type now, and dedupes.

- **Nothing told the agent to read a value before overwriting it.** The review caught the
  damage: wall Marks cleared across the model with the originals never captured, and an offset
  reset to `0` on the assumption that `0` was what had been there. Both are *behaviour*, not a
  code path — a write commits and the previous values are gone. `ping` and the system prompt
  now say, in the write section, to read the current value first and report old → new, and
  never to call a value "the original" unless it was actually read. Read-only mode is the
  safer half of the same fix: discovery runs in a rolled-back transaction group.

- **View exports accumulated in `%TEMP%` forever.** Every `export_view` wrote a fresh PNG into
  `%TEMP%\paracore_views` and nothing ever removed one — the review's "temp file left in
  Windows Temp". Exports older than **7 days** are now pruned at the start of the next export.
  The predicate is deliberately narrow: that directory, the `view_` prefix this tool writes,
  an image extension. A file Paracore did not write is left alone.

### Not reproduced

- *"`GetStr` on a missing parameter warns once per element, flooding Peek."* The warning is
  deduplicated per parameter name in the shipped engine, and was measured firing **once per
  name**, not once per element. If it recurs, the output is needed to chase it.

### Known limitations

Stated in the README rather than implied: a target type name assembled at runtime is refused
now because the reflection *entry points* are blocked, but `dynamic` dispatch and a delegate
obtained from a framework method are not reasoned about; the network ban is the same keyword
list; the timeout fires only at a loop-body check, so a single blocking call or a loop inside a
framework method is not interrupted; the dialog watcher will answer dialogs you did not expect;
and workshared and very large models are untested.

## From the second pre-release review

A second pass against the rebuilt add-in confirmed the first round: discovery rollback discards
a reflection-built `Transaction` + `Parameter.Set` **and** `Document.Save`; a plain `while` loop
is killed at 90 s; `GetNum`/`OutputUnit` are exact (5.065 m, 2032 mm → 2.032 m); `WhereParam`
and the read-before-you-write guidance work. It found four more things.

- **A script's last line could disappear.** Text output was cut at the first 20 lines, so the
  final `Println` — conventionally the result — was the first casualty ("2 more lines not
  shown"). Text now keeps the **first 12 and last 8** lines and elides the middle, matching
  what tables already did with `TABLE_TAIL_ROWS`.

- **An empty parameter was reported as a misspelling.** `GetStr` warned "parameter not found …
  check spelling" whenever no scope produced a *value*, which is not the same as the parameter
  not existing. An existing-but-empty parameter fell through every fallback and triggered it —
  about five times on a single `Peek()`. It now checks whether the element or its type
  *declares* the parameter before claiming it is missing.

- **The reflection bypasses are closed at the entry point, not the target.** The review defeated
  every file/network/process pattern by assembling the type name from string pieces:
  `typeof(object).Assembly.GetType("System." + "IO." + "File")`. Splitting a string hides the
  target; it cannot hide the mechanism. The policy now refuses `Type.GetType`, `Activator`,
  `.Assembly`, `System.Reflection`, `GetMethod`, `MethodInfo`, `InvokeMember`, `DynamicMethod`,
  `DllImport` and `Marshal` — so a runtime-built name has nothing left to resolve it with.
  ⚠ Still a list, not a sandbox: `dynamic` and framework-supplied delegates are not covered,
  and the README says so.

- **Two ways to freeze Revit that the loop guard could not see.** `Thread.Sleep(100000)` ran its
  full 100 s — now refused outright, since sleeping has no use in a takeoff script. A spin
  inside a block-bodied lambda (`list.Where(x => { while (…) { … } return true; })`) was never
  visited by the rewriter; lambdas are now checked too.
  Measured on the built engine rather than assumed: the check lands at the lambda's **entry** as
  well as inside its loop, so `Enumerable.Range(0, int.MaxValue).Select(x => { … }).ToList()` —
  a loop the rewriter cannot see at all — is still interrupted, because the lambda is re-entered
  on every iteration. Expression-bodied lambdas are left byte-for-byte alone.
  ⚠ Residual, documented: a framework loop with no block-bodied lambda in the path
  (`Enumerable.Range(0, int.MaxValue).ToList()`) still runs to the end, and so does deep
  recursion. Cancelling a thread mid-call needs a separate process, which .NET 8 does not
  support without `Thread.Abort`.

Verified live this round, not merely rebuilt: `search_schema("Doors")` lists **`Level` once**
(no `Level [Reference]`), and a bad view name now lists `Level 1 (FloorPlan)` and
`Level 1 (CeilingPlan)` — distinguishable, where it used to print `Level 1` twice.

## From the third pre-release review

A third pass found the worst category of defect for a tool that edits models: two ways to write
a wrong value and report success. Both are closed. The rest of the round is documentation that
taught a call which does not compile, and a handful of cosmetic drifts.

### Silent wrong writes

- **An unknown unit was treated as "already in feet".** `SetNum("Base Offset", 5, "furlongs")`
  committed **5 feet — 1524 mm** — because the unit resolver returned `null` for anything it did
  not recognise, and `null` meant "no conversion needed". A typo and a deliberate no-conversion
  were the same value. The resolver now throws, names the offending string, and lists what is
  supported (`mm, cm, m, in, ft; m2, ft2; m3, ft3`). The empty string stays legal — that is the
  documented escape hatch for a value already in internal units, and it is now the *only* way to
  say so. ⚠ A display helper refuses an unknown unit too: `FormatUnit` would otherwise print a
  converted-looking number beside a label it never applied.

- **`SetVal` looked up a name without checking what the parameter accepts.** The old code took the
  first element *anywhere in the document* whose name matched and wrote its id. `SetVal("Top
  Constraint", "None")` therefore resolved to whatever happened to be called "None" — in the
  review, a Phase — and wrote it. The wall read back `None` with a **changed height**, which is
  the signature of a silent wrong write: plausible text, wrong model. Now the search is confined
  to the categories the parameter can hold (level/constraint → Levels, view → Views, phase →
  Phases, material → Materials); a name that matches more than one element is **refused** with the
  candidates listed rather than resolved to the first; and a numeric id must name a real element
  of an acceptable kind. Nothing is guessed.

- **`"Unconnected"` and `"<None>"` did nothing; `"-1"` worked by accident.** The three spellings
  that mean "no reference" are now honoured *before* any lookup, so they can never be confused
  with an element that shares the name. A bare `"None"` that matches nothing acceptable clears the
  reference — which is what it means — instead of writing a same-named element of the wrong kind.

### A matcher that missed half the model

- **`WhereMatches`/`Matches` never saw family names.** `WhereMatches("Basic")` returned **0** on
  nine walls whose `FamilyName()` is "Basic Wall", because the check short-circuited through
  `is FamilyInstance` and skipped host elements such as walls. It now matches element name, family
  name and type name. `FamilyName()` reads `ELEM_FAMILY_PARAM` with a fallback, so it works for
  system families too. ⚠ Still a name matcher, not a parameter matcher: use `WhereParam("contains")`
  for values.

### Documentation that taught a call which does not compile

- **`.Where("Count", ">", 5)` after `GroupByParam` — CS1501.** `GroupByParam` returns
  `IEnumerable<object>`, and no extension overload exists on that. `aggregate-group` and the
  catalogue both showed it. Both now show the call that compiles, verified by running it:
  `.GroupByParam("Level").Cast<dynamic>().Where(g => g.Count > 5).Table()`.

- **`read_extension_methods()` with no query was cut mid-snippet** while its description called it
  the complete ~17,000-character catalogue. The head is now cut on a section boundary and says so:
  it names the character count and tells the caller to pass a query for one method or section.

- **`create-geometry` pointed at three skills this server does not have** (`project-modeling`,
  `paracore-model`, `family-authoring`). It now inlines the two recipes it was pointing at, and
  says `list_skills` is the authoritative list of what *this* server teaches — if a recipe is not
  among them, it is not here.

- ⚠ **The same dead pointer was in the live system prompt, and every gate was green.** Fixing
  `create-geometry` left `mcp_server.GEN_INTRO` still telling the model that "the `paracore-model`
  and `paracore-family` MCPs are the specialists" — and `GEN_INTRO` is not a skill and not a
  prompt file: it is the block concatenated into `build_instructions()` and delivered on every
  session, i.e. the most-read text in the product. The reference gates all scanned `skills/` and
  `prompts/`, so the defect was invisible to them. There is now a gate on the **delivered string**
  (`tests/test_skill_references.py::TestLiveInstructions`, teeth proved by reintroducing the
  pointer), and two checks in `spikes/verify_export_view.py` that used to *assert* the pointer
  existed are inverted to assert it is gone.

### The skill set was wrong for this server, and stale files were keeping it wrong

`paracore-model` is what models. `paracore-gen` is the generalist: it does its work by
generating REPL on the fly, with full access to the raw Revit API, LINQ and the Paracore DSL,
and `GEN_INTRO` states which to prefer. So this server no longer ships `create-geometry` — the
skill is filtered out of its catalogue (`Domain.shared_skills`), not deleted, because
`paracore-model` and `paracore-family` still need it. Its catalogue is now exactly the eight
non-modelling method skills, and a gate asserts the two halves together: absent here, still
present in the core.

That change exposed the real cause of a week of confusing reviews: **nothing is deleted when an
implementation is replaced.** `prompt_assembler.build_prompt()` assembled ten `prompts/*.md`
files into a ~36,000-character system prompt. When the shared core moved here, the live channel
became `server.build_instructions()`, and from that day nothing called `build_prompt()` again —
but the function, the ten-file list and the files themselves stayed on disk and shipped in every
installer. Measured against the four channels that ARE read (the handshake's 4,480 chars, the
tool descriptions, the skill bodies, and the reactive error text in `tool_helpers.py`), eight of
the ten files had no reader at all.

They are deleted, and so is `build_prompt()`. Two things were rescued first, because deleting
them would have lost content rather than tidied it:

- `verification.md`'s behavioural rules had no replacement anywhere — "verify before the next
  call", "the same call failing twice means the approach is wrong", "three attempts then stop".
  They are now a short `VERIFY BEFORE YOU BUILD ON IT` block in `COMMON_RULES`, so they reach
  every session instead of no session.
- `globals.md` was reachable only as the `paracore://globals` **resource**, and resources are
  never read by the clients this server targets. So `Doc.ProjectInformation`,
  `Doc.PathName` and `Doc.IsWorkshared` appeared in no tool, no skill, no instruction and no
  engine doc — which is why "workshared models" could never be tested: the agent had no
  documented way to ask. `get_globals` is a **tool** now (5,373 characters), and the resource
  stays for clients that do read them.

`paracore-family` lost its three prompt overrides and its copies of the same files, and
`SKILLS.md` was removed from this repo: it is generated from the full shared set, so it could
not see the Domain's filter — the moment `create-geometry` was dropped, the file still listed it
and still said "nine". A generated doc that cannot see the filter is a second copy of the truth,
and a stale one is worse than none.

### Minor, all corrected

`FormatUnit` returned `m2` where a quantity surveyor writes `m²` (areas and volumes now render
`m²`/`ft²`/`m³`/`ft³`, and a gate keeps the display map in step with the resolver);
`search_schema` printed a bogus example snippet after an unknown-category error and its snippets
used `Id.IntegerValue`, which this project forbids in Revit 2025+ (now `Id.Value`, and the example
only prints when there is a result); `ExportImage` was documented as always writing `.jpg` when a
3D view came back `.png` (the doc now says the extension is chosen for you and must not be
assumed); and `SumParam` was documented as rounding to 3 decimals while returning
`13.279647179999975` — it is exact by default, and the docs match.

### First live Claude Desktop session — four findings, all fixed

A full agent session against a test model (about a dozen calls: reads with unit conversion,
bulk `SetParam`, raw-API creation inside `Transact`, rollback on exception, hide/delete, the
timeout watchdog, `export_view`) found four defects. Everything else it exercised worked.

- **A misspelled parameter in `GetNum` returned 0 in silence.** `GetStr("Fire Ratng")` warned;
  `GetNum("Unconnected Hieght", "m")` returned **0** with no warning at all, so a typo was
  indistinguishable from a real zero. For a quantity that is the worst failure available — a
  BOQ line reading 0 m² looks like a measurement. `GetNum` and `GetInt` now warn exactly as
  `GetStr` does, and all three name the **closest real parameter** ("Did you mean
  \"Unconnected Height\"?"). The warning prints once per name and then every 25th element, so a
  typo across 900 elements says "the name is wrong for this whole set" instead of either
  printing 900 lines or hiding behind one.
- **Compile-error line numbers were 2 high while claiming to be the user's.** A missing `;` on
  the user's line 8 came back as `script(10,1)` and was rendered "engine line 10 … outside your
  snippet", under a header asserting those were the user's own numbers. A diagnostic outside
  the `#line` region is reported in physical coordinates but still carries the filename, which
  is the marker the annotator trusted. The shift is constant within a submission, so it is now
  detected once — from the provable case, a number past the end of the snippet that lands
  inside it after subtracting the prelude — and applied to the whole batch. Numbers that are in
  range but shifted cannot be detected from here and are left alone rather than guessed at.
- **The bulk-write warning fired on single-element calls.** `doors.First().Hide()` was reported
  as "bulk hide on ALL filtered elements" — the scan matched `.Hide(` and never looked at the
  receiver. A call whose chain ends in a single-element selector (`First`, `Single`,
  `ElementAt`, `GetElement`, `ToElement`, …) is no longer flagged. ⚠ The scan still cannot
  follow a variable (`var d = doors.First(); d.Hide();` warns), and that is written into the
  tests rather than hidden: a false positive is noise, a silent miss on a real bulk delete is
  data loss.
- **The convention note fired on correct code.** `new FilteredElementCollector(Doc).OfClass(
  typeof(Level))` was nudged toward a typed route the reviewer could not confirm existed. It
  does — `GetElements<Level>()` runs `OfClass(typeof(Level))` underneath
  (`ParameterOptionsComputer.CreateResilientCollector`, quirk 3) — so the rule was right and the
  message was not: it now names `GetElements<Level>()` and the `FirstOrDefault(l => l.Name ==
  "Level 1")` form explicitly.

### How much of this is verified

Two categories, kept apart on purpose:

- **Verified now, without a Revit session.** Both projects compile with 0 errors. The unit-display
  map is checked by a source-level gate (`scripts/check-unit-display-parity.py`) that proves every
  one of the 39 accepted spellings has a canonical suffix — and the gate's own teeth are proven by
  running it against five deliberately broken copies (dropped label, digit suffix, invented unit,
  renamed method, gutted vocabulary) and requiring the right exit code for each.
- **Needs the rebuild, then the REPL.** The unit refusal, both reference-write paths and the family
  matcher are behaviour, not text, so no source-level check can settle them. They are exercised
  against the installed build immediately after the rebuild: `SetNum(..., "furlongs")` must throw;
  `SetVal("Top Constraint", "None")` must clear the constraint rather than write a Phase;
  `WhereMatches("Basic")` must find the walls. Until that run happens, this section is a claim
  about code and a compile, not a claim about behaviour — and is written as such.

## From the fourth pre-release review

A fourth pass focused on one thing: the MCP's table cap (50 rows) was cutting parameter schemas
in half. A `search_schema("Doors")` that returned 80 parameters looked like it returned 48 —
the last 30 were silently dropped, and the "more rows not shown" trailer did not say which ones.
For a tool whose job is to tell the agent what parameters exist, that is the worst failure mode:
a real parameter looks missing.

### Schema tables are never truncated

- **`CombinedParams()`, `InstanceParams()`, `TypeParams()`, `BuiltInParams()`, `NativeProperties()`
  are now exempt from the 50-row cap.** These are schema/discovery methods — the list IS the answer,
  and cutting it makes a real parameter look missing. The exemption travels as a `cap_exempt` flag
  on the wire (`StructuredOutputItem.cap_exempt`, proto field 4), set by the engine and read by the
  summarizer. The producer decides, not the consumer: the summarizer never infers "schema-ness"
  from column names.

- **The marker is `SchemaRows`.** A `SchemaRows` wrapper around the `IEnumerable<object>` tells
  `Table<T>` "this is a schema, show it whole" without changing the discovery methods' call shape.
  The marker is lost by `Select`/`Where`/`ToList` — deliberate: once you transform the rows, they
  are no longer a schema, they are a computed result, and the cap applies again.

- **`Peek()` is exempt too.** A parameter dump on a single element is small but uses the same
  table path; it emits with `capExempt: true` directly.

- **Element dumps still cap.** A `.Table()` on 200 walls still caps at 50 rows with the head +
  tail + "more rows not shown" trailer. The exemption is for schemas, not for element renderings.

### `pick_object` removed from this server

- **`pick_object` was a gallery concern, not a REPL concern.** The `pick` mechanism lives in the
  `Params` class (`[Select(SelectionType.Element)] public Wall? TargetWall`), which is only
  available in compiled gallery scripts — not in the REPL. In the REPL path that `paracore-gen`
  serves, the agent addresses elements by id, or the user selects in Revit and the agent reads
  `Selection` (a REPL global). `pick_object` is now omitted from gen's tool surface via
  `omit_common=("pick_object",)`. It stays registered for servers that want it.

### Documented which tables are never truncated

- **The `ping` cheat-sheet now has a TRUNCATION section.** It states which tables arrive whole
  (schema/discovery) and which cap at 50 rows (element dumps, query results). The
  `explore_revit_data` docstring and the catalogue prompt carry the same note.

### How much of this is verified

- **Verified now, without a Revit session.** Engine and add-in compile with 0 errors. The Python
  suite is 120/120 (11 new tests for the cap exemption). The cap-exempt teeth probe proves the
  exemption has teeth in **both** directions: forcing it off makes 4 tests go red (schema tables
  would be capped); forcing it on makes 5 go red (element dumps would escape the cap). The proto
  gate confirms `cap_exempt` field 4 is in the wire type. The MCP-exe gate's sentinels are
  retargeted for round 4 (`summarizer.py` → `"shown in full"`, `tools.py` → `"TRUNCATION"`,
  `server.py` → `"omit=omit_common"`).
- **Needs the rebuild, then the REPL.** The cap exemption is behaviour — no source-level check
  can prove a 80-row schema arrives whole. After the rebuild: `search_schema("Walls")` on a model
  with >50 parameters must say "shown in full" with no "more rows" trailer; a `.Table()` on 100
  elements must still cap at 50 with the trailer.



## From the fifth pre-release review

A fifth pass, this time as a public reader would meet it. It reported seven things. **Two of them
were already fixed in the source and were re-reported from the previous build** — the review ran
against the installed exe from 10:27, while the source had been corrected at 11:47. Both
`.Id.IntegerValue` in the schema template and the usage block printed under a "no parameters
found" error are correct in this build; they are verified below rather than "fixed" twice.

The five that were real, and two that the review did not catch:

### The schema example named a parameter the category does not have

The worst of them, and it was the review's own advice turned against it. `search_schema` ends with
a runnable example, and the example was a **fixed template**:

```csharp
GetElements("Walls").Select(e => new { Id = e.Id.Value, Level = e.GetStr("Level"), ... })
```

`Level` is correct for Rooms, Doors and Windows. **Walls have no `Level` parameter at all** — 62 of
them, and the nearest thing is `Base Constraint`. `GetStr` on a name that does not exist returns
`""` with no error, so the example **compiled, ran, and produced a column of blanks** — the silent
empty-column failure this server spends a paragraph warning about, shipped as its own advice,
printed two lines under the parameter list that proves it wrong.

- The example is now **derived from the rows above it**. `schema_cache.schema_rows()` is the single
  definition of what a row is; the list and the example are built from the same list, so the example
  cannot name a parameter that is not there.
- **The unit is chosen with the parameter, not bolted on.** `GetNum(name, "m2")` on a parameter that
  is not an area does not throw — it converts the raw number as if it were square feet (measured:
  `GetNum("Absorptance", "m2")` returned `0.065` instead of `0.7`). Only a parameter whose unit is
  unambiguous from its own name gets one; anything else is omitted rather than guessed.
- Column names are made into legal C# identifiers (`Heat Transfer Coefficient (U)` is a real Walls
  parameter).

### Float noise in every table

`3.0000000000000004` — nine identical 3 m walls, one rendered `3` and eight rendered
`3.0000000000000004`. The number was right; 3 m stored as feet does not come back to exactly 3. The
**rendering** made one wall look different from its neighbours.

- Floats now render at 12 significant digits, which is more than any Revit quantity carries (a
  micron inside a 1 km building needs 9). Trailing zeros drop: `3.0` → `3`, `14.520000000000001` →
  `14.52`, and a genuinely precise value is untouched.
- **The totals line uses the same formatter.** It was `%.2f`, so a total could print `35.81` over
  rows summing `35.806` — a total that visibly disagrees with its own column, leaving the caller to
  guess which number to believe.

### `paracore://system-prompt` — a pointer nobody can follow

Error messages told the agent to "read `paracore://system-prompt`". The review could not confirm the
resource existed. It does — and it is **inert on the client this server targets**: over 70 Claude
Desktop sessions, `resources/read` was called **zero** times. It also holds the rules, not the method
catalog the message promised.

- Those messages now name the **`_read_extension_methods` tool**, which every client can call.
- The same messages also said `read_extension_methods(...)` — **a tool that does not exist**; the
  registered name carries a leading underscore. Fixed in all four places, because a wrong tool name
  in an error message is a dead end for an agent that is already failing.

### Dead references to products this server does not ship

`create-geometry` told the reader to run `read_skill("project-modeling")`, and pointed at a
`paracore-model` and a `paracore-family` MCP. Neither is in this catalogue and neither is obtainable
by a public reader — the call simply fails.

- The pointers are gone. What was worth keeping is stated inline: build a building **per level**
  (levels → slab → walls → rooms, then the next level), and a `Form` cannot become a wall, floor or
  room. `list_skills` is named as the authoritative list.

### Working notes in text that ships to every user

- Removed: `25.00 Birr` (a private example value, in three places — including the **method
  reference**, whose authority is `paracore/EXTENSION_METHODS.md`; the copies were regenerated),
  "on the house model", "Measured 2026-10-08", a changelog aside about `.jpg` vs `.png`, two
  references to a **Pro add-in**, and `33 standard doors (out of 40 total)` — a fact about one
  model, presented as a result.

### How much of this is verified

- **Verified now, without a rebuild.** The Python suite is **144/144** (24 new). The new gates are
  class-based, not string-based: `test_skill_references.py` asserts that **any** `read_skill("X")`
  in any skill resolves in the catalogue, that no foreign product is named, that no `paracore://`
  pointer survives, and that no dated or private note remains — proven with teeth by reintroducing
  the defect, which turns 3 of its 6 tests red. `TestUsageExample` asserts the generated example
  only names parameters present in the rows (the Walls/`Level` regression is one of its cases).
  `TestNumberRendering` proves both directions: the noise is gone **and** a 12-digit value survives,
  and it fails on the old formatter.
- **The generated example was executed, not just inspected.** On the live model,
  `Walls`, `Doors` and `Structural Columns` each returned a real table with non-empty columns;
  `Floors` and `Structural Columns` have no instances in the sample, and reported that instead.
- **Repo gates all pass**: 187 `csharp` fences compile across 5 repos; the engine-doc generator
  reports all 13 copies in sync after the `Birr` removal; the session-gate caption gate, the unit
  display map and the memory budget all pass.
- **Needs the rebuild, then a client.** Nothing above is visible until the exe is rebuilt and
  installed — the skills and prompts are **bundled data**. After the rebuild: `search_schema("Walls")`
  must show `Type_Name`/`Area`, never `Level`; a `GetNum` column must read `3`, not
  `3.0000000000000004`; and `read_skill("create-geometry")` must not mention another product.


The shared core is not vendored here. The build resolves it from a sibling `paracore` checkout
(`../paracore/mcp`), or from `PARACORE_MCP_CORE` if you set it. Its **skills and prompts are bundled
as data** under `mcp_core/…`, and `VERSION` must be added by the build CLI rather than the spec —
both are enforced in `build-gen.ps1`.

## Consent, reported rather than assumed

- **The agent learns what the operator chose.** Every execution result now carries
  `session_consent` — `granted`, `already_granted`, `denied` or `not_required` — so the tool output
  states who allowed the run instead of returning a bare success. A denial is terminal: the agent is
  told the operator blocked it, that nothing ran, and not to retry or work around it.

- **The session gate is read, not guessed.** `GetStatus` reports the session's consent
  (`unsettled` / `granted` / `denied`) over the new wire field 10, and this server asks before every
  agent call. The gate is per **Revit session**, not per server, so a session another MCP already
  had allowed is no longer mistaken for a fresh one — which used to make a long first call look like
  a consent dialog that was never going to appear.

- **A deadline that says which deadline it was.** A call made while the session is ungated is capped
  at **60 s**, because only a person can end that wait; once the gate is settled the call keeps its
  normal deadline. The error text names the cause rather than listing both, and the next call is
  cheap and definitive because the gate latches its answer.

## Requirements

**Paracore Add-in v4.8.1** installed and running in Revit — the two are released together.

⚠ **The consent-gate fix needs both halves.** The add-in asks with captions the watcher does not
recognise; the watcher is the one that must decline to answer. **Gen 2.1.0 against add-in 4.8.0 still
auto-approves**, because 4.8.0's dialog offers `OK` — a label the watcher presses on sight. Upgrade
the add-in as well, or the prompt stays decoration.
