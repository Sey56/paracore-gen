# Paracore-Gen

The generalist Model Context Protocol server for Paracore — enables Claude Desktop,
Cursor, VS Code, and any MCP-compatible client to explore and control Revit through
natural language.

⚠ The product is **`Paracore-Gen`** on every surface (renamed 2026-10-09, from
`Paracore-MCP`): repo, build script, exe, installer, `UninstallDisplayName`, the
`FastMCP(...)` handshake and the client's config key. See
`paracore-ecosystem/MASTER_SYSTEM_SPEC.md` → **"PRODUCT NAMING"**.

## What it does

Connects to the Paracore Addin running in Revit (via gRPC on `localhost:50051`)
and provides MCP tools for running C# code dynamically:

- **`ping`** — verify connection to Revit
- **`get_context`** — active view, current selection, project levels
- **`export_view`** — render a Revit view to an image so the agent can SEE the model
- **`_explore_revit_data`** — run C# for discovery; obvious model writes are refused
- **`_execute_dynamic_query`** — run read-write C# with auto-transaction wrapping
- **`_search_schema`** — fast parameter schema lookup per Revit category
- **`_read_extension_methods`** — the full Paracore extension methods catalog
- **`list_skills`** / **`read_skill`** — the eight-skill catalogue and its text

⚠ This is the **generalist** server: it generates and runs a REPL script for *any*
Revit task. It prefers the Paracore extension methods, but the **raw Revit API, LINQ
and .NET** are all in scope when the methods are not enough. It is deliberately not
the deep specialist for modelling or families; those belong to separate
domain servers.

## What a snippet can reach

Agent code runs as C# inside Revit's own process, with `System` already imported. `System.IO`
is **not** — it is refused at the symbol level on this channel, so a snippet cannot name a file
API at all (see "Files" below for why, and for what that costs). That is a real capability
either way, so it is **refused at the point of submission** rather than trusted: `paracore-gen`
scans every snippet before it is compiled, and the add-in scans it a second time so a direct
gRPC caller cannot skip the first check. The two lists are the same list, in the same order — a
test fails if they ever diverge.

⚠ **The consent dialog decides WHO may run agent code. It is a decision, not a second line of
defence** — do not read "the human clicked Allow" as protection.
**It asks once per Revit session, not once per snippet**, and that is deliberate. A per-write
prompt would fire on every step of a multi-step edit, and a prompt that appears twenty times in
a row does not produce twenty judgements — it produces one reflex. The protection that has to
hold when nobody is reading the dialog is the sandbox, which is why the sandbox is the thing
built to hold without a human in the loop.

⚠⚠ **The scan is a FILTER, not a sandbox.** It refuses the forms listed below and nothing
else: a call it does not name, a name assembled at runtime, or a type reached through a
reference the compiler was given will not be refused. Treat it as a mistake-catcher that stops
the common accident — not as a boundary that stops a determined script. What a snippet can
*name* is decided by the reference set, not by this list, and the list is the wrong place to
look for the boundary. `tests/test_scan_coverage.py` holds this page to exactly the claims it
makes; a rule that stops matching fails there, not in production.

⚠ **This list is the REPL entry point's list.** It is enforced on `execute_repl` — the path a
chat snippet takes — by this package's scan and by the add-in's mirror. A gallery script
submitted through `execute_script` is compiled as an installed tool
and is **not** subject to the file/thread list here: an installed tool may legitimately write an
output file at runtime, so a blanket file ban on that path would refuse it. What **both** paths
share is the semantic sandbox (`ScriptSandbox`), which refuses process, network, registry,
native code and reflection at the symbol level regardless of caller — measured on both entry
points, not assumed. **That is the boundary; this list is the filter on top of it.**

**Refused outright — no agent snippet reaches these** (on `execute_repl`):

- **The network.** `HttpClient`, `WebClient`, `WebRequest`, `HttpRequestMessage`, `Socket`,
  `TcpClient`, `UdpClient`, `Dns`, `SmtpClient`, `Ping`, `RestSharp`, and the whole
  `System.Net` namespace.
- **Processes, threads, the registry, native code.** `Process.Start`, `ProcessStartInfo`,
  `new Thread`, `Microsoft.Win32.Registry`, `DllImport`, `Marshal`,
  `System.Runtime.InteropServices`.
- **Reflection — the whole family, not a sample of it.** `AppDomain`, `GetAssemblies`,
  `GetTypes`, `GetConstructor(s)`, `GetMethod(s)`, `GetProperty`/`GetProperties`,
  `GetField(s)`, `GetMember(s)`, `GetNestedType`, `Activator`, `System.Reflection`,
  `.Assembly`, `MethodInfo`, `ConstructorInfo`, `CreateDelegate`, `DynamicMethod`, and the
  `dynamic` keyword — with one exception, `Cast<dynamic>()` on grouped rows, which the
  aggregate recipe needs.
  ⚠ The scan refuses the **entry point**, not the target name, because a name can be assembled
  from string pieces at runtime while the act of enumerating an assembly cannot be hidden.
  (An earlier round refused only `Type.GetType` / `Activator` / `.Assembly` / `GetMethod`, and
  a review walked straight past it with `AppDomain.GetAssemblies()` → `GetTypes()` →
  `GetConstructor(...).Invoke(...)`.)
- **Any file access at all** (widened 2026-11-01). `System.IO` is refused at the symbol level,
  so `File.*`, `Directory.*`, `FileInfo`/`DirectoryInfo`, `FileStream` and `StreamWriter` cannot
  be named — read, enumerate, stat or create. The list below still describes what the text scan
  refuses, but on this channel the scan is now the *second* line, not the first. See "Files"
  further down for the measurement that forced this and what it costs.
- **Sleeping.** `Thread.Sleep` — a blocking call cannot be interrupted by the timeout, so it is
  the one measured way to freeze Revit from a snippet.

⚠ **The scan reads CODE, not prose.** Comments and string literals are blanked before it runs,
so a comment that says "never call `Process.Start`" is not itself a violation. (It used to be.)

- **The model — one layer is a guarantee, one is a guess.**
  - `_explore_revit_data` runs the whole snippet inside a **transaction group that is
    always rolled back**, so a model write is *discarded by Revit itself* however it was
    reached — through reflection, inside the snippet's own nested transaction, or by any
    route the scan cannot see. That layer is an invariant, not a pattern match.
  - In front of it sits a **pattern scan** that refuses the obvious raw-API writes
    (`new Transaction(...)`, `Parameter.Set(...)`, `Doc.Delete(...)`) with a clear message.
    That layer is a mistake-catcher: a call assembled through reflection passes it.
  - `_execute_dynamic_query` is the write path and is intentionally unrestricted.
- **A value is validated before it is committed.** The write path does not guess:
  - An **unrecognised unit throws**. It used to mean "already in feet", so
    `SetNum("Base Offset", 5, "furlongs")` committed 5 feet (1524 mm) and reported success. An
    empty unit string is the one explicit way to say "no conversion".
  - A **reference written by name** is looked up only among the categories that parameter can
    hold (level/constraint → Levels, view → Views, phase → Phases, material → Materials). A name
    matching more than one element is **refused with the candidates listed** rather than resolved
    to the first hit, and `"None"` / `"<None>"` / `"Unconnected"` / `"-1"` clear the reference
    instead of being searched for. Writing a same-named element of the wrong kind — how
    `SetVal("Top Constraint", "None")` once wrote a Phase and changed a wall's height — is no
    longer reachable.
- **Files — one folder, and only one** (changed 2026-11-01, measured, then relaxed the same day).
  A snippet cannot name `System.IO` at all, so it cannot read, enumerate, stat or create a file
  anywhere. File *work* is still possible, through `ScriptApi.Files`, which confines every path
  to a single workspace folder — `Files.Root`, `%LOCALAPPDATA%\Paracore\AgentWorkspace`, movable
  with `PARACORE_AGENT_WORKSPACE`:

  ```csharp
  Files.WriteText("takeoff.csv", csv);        // inside the workspace
  var text = Files.ReadText("input.csv");
  foreach (var p in Files.List()) Println(p);
  Files.Delete("scratch.txt");
  ```

  - **Why a façade, and not "`System.IO` allowed under a folder".** A path can only be checked
    where its *value* exists. The sandbox is a compile-time symbol walk: `Path.Combine(root, name)`
    says nothing about `name`, and `..`, a junction, a `\\?\` device prefix or an alternate data
    stream defeats any static test — leaving a boundary that looks real and is not. `Files`
    canonicalises the path, rejects device paths, streams and Windows device names, resolves every
    reparse point, and re-checks containment against the *resolved* target. At runtime.
  - **Why the `System.IO` ban stays.** Creation was a persistence primitive. `FileMode.CreateNew`
    worked, and `C:\ProgramData\Autodesk\Revit\Addins\2025` grants
    `BUILTIN\Users:(CI)(WD,AD,WEA,WA)` — Users may create files there. A `.addin` manifest planted
    in that folder is loaded by Revit at the **next launch**, with no sandbox and no consent. A
    file outlives the run, so the workspace is the only place one may land.
  - **Reading was an egress channel.** Enumeration and existence probes worked against `C:\`, the
    user profile, the Chrome profile and the Revit Addins folder, and `Environment.UserName`
    returned the account name. Whatever a snippet reads is returned in the tool output, to the
    model provider — the network block does not cover that path.
  - **Still refused:** anything outside the folder, deleting the workspace root itself, and the
    Revit calls that write or read a file at a path you name — `SaveAs`, `Export*`,
    `OpenDocumentFile`, `LoadFamily`, `Import`. Revit performs those writes itself, so no
    reference-set rule can see them; they would be the last route out. `ExportImage(...)`, the
    engine helper, is *allowed* because it routes its target through the same guard.
  - A **gallery tool** run from the desktop app still has full file access — an installed tool
    may read and write its own output files, and that is the product working.
  - ⚠ This is a **channel** distinction (which gRPC entry point), not a trust level attached to
    the `source` string. See `ScriptSandbox.ReplChannel` and
    `ExecutionGlobals.ConfineFileAccess`.
- **A human is not an agent — but the REPL channel is still the REPL channel.** The text scan is
  keyed on the call's `source`, and only sources containing `agent` are held to it. The
  `System.IO` refusal is **not** keyed on `source`: it is a property of the `execute_repl` entry
  point, so a snippet *you* type there has no file access either. That is deliberate — the
  desktop app runs saved scripts and gallery tools through `execute_script`, which keeps full
  file access, so an installed tool that reads and writes its own CSV is unaffected.

### Known limits, stated rather than implied

| Limit | What it means |
|---|---|
| It is a deny-list, not a sandbox | Every capability above is refused by name, and the entry points are refused rather than the target types. The **delegate** gap is now closed at the binding call (`Delegate.CreateDelegate` is refused, and the closed reference set leaves no route to a banned *type*: measured, `using T = System.Type; T.GetType("System.IO.FileStream, …")` is caught by the symbol walk). Code hidden inside an **interpolated-string hole** is not reasoned about. |
| A single framework call cannot be interrupted | Confirmed by an external review (2026-11-01): `SetExecutionTimeout(1)` did **not** stop `Enumerable.Range(...).Count(...)`; the call ran 2.5 s and would run as long as it liked. The injected budget only reaches loops and block-bodied lambdas **in your own code**, so a framework loop with no lambda in the path is a **denial of service, not an escape** — nothing outside the workspace becomes reachable, Revit just stops responding. The only real fix is out-of-process execution, which is not this release. |
| Runaway code has a budget, not a kill switch | A timeout check is injected at the top of every loop body **in your own code**, and at the entry of every **block-bodied lambda** — so `…Select(x => { … })` is guarded even when the loop itself lives inside the framework call. Default **90 s**; raise it with `SetExecutionTimeout(n)` as the first statement. Not interrupted: a single blocking call (`Thread.Sleep` is refused outright for exactly this reason), a framework loop with **no** block-bodied lambda in the path — `Enumerable.Range(0, int.MaxValue).ToList()` runs to the end and Revit stays frozen — and deep recursion. A wedged Revit is ended by restarting Revit. |
| The dialog watcher presses buttons | A resident thread answers Revit's modal dialogs so a blocked call can return, and reports what it pressed. It will also answer a dialog you did not expect. Kill switch: `PARACORE_WATCH_DIALOGS=0`. |
| Workshared and very large models are untested | The review ran against a small single-user model. |
| Units are a fixed vocabulary | `mm, cm, m, in, ft` and `m2, ft2, m3, ft3`, plus their long forms (`square meters`, `cubic feet`, …). Anything else **throws** rather than being assumed to be feet. An empty unit means "already in internal units" and is the only way to skip conversion. |
| A reference written by name is matched within an inferred category | The category comes from the parameter *name* (`level`/`constraint`, `view`, `phase`, `material`). A parameter whose name matches none of those accepts any category but still refuses ambiguity — so if two elements share the name, set it by id. |

Tool output contains the **project file path**, because the agent needs to know which
model it is in. It deliberately does **not** contain the Windows user name or the
Revit install path.

## Build

```powershell
./build-gen.ps1
```

Requirements: Python 3.12, Inno Setup 6. The **shared core is not in this repo** — it
is `mcp_core` from the **`paracore-mcp-core`** repository, imported as a package,
so `paracore`, `paracore-mcp-core` and `paracore-gen` must be **sibling checkouts**
under one parent directory (override with `PARACORE_MCP_CORE`).

Produces: `installers/Paracore-Gen-v2.1.2.exe`

## Install

1. Install the **Paracore Addin** from the [v4.8.3 release page](https://github.com/Sey56/Paracore/releases/tag/v4.8.3)
2. Run `installers/Paracore-Gen-v2.1.2.exe`
3. Configure Claude Desktop to use the MCP server

## Structure

```
mcp_server.py        The DOMAIN only — product name, instructions, no skills of its own
REPL_GUIDE.md        Engine REPL reference (generated copy; authority is paracore/)
EXTENSION_METHODS.md Engine API reference (generated copy; authority is paracore/)
tests/               pytest — the guards, the linters, the summarizer
build-gen.ps1        PyInstaller build → installers/
```

⚠ The tools themselves are **not here**. `mcp_core/` — the tools, validation, skills,
prompts, summarizer, gRPC client — lives once in the sibling `paracore` repo at
`mcp/mcp_core/` and is imported. One fix there reaches every MCP.

## Skills

Eight operation-based skills replace the monolithic extension methods catalog. Each is
a focused `SKILL.md`. They are served as **tools**, not resources: Claude Desktop does
not read MCP resources, so the agent calls `list_skills` and then `read_skill("<name>")`.

⚠ These cover the Paracore **extension methods**. Deep **modelling** and **family
(.rfa)** recipes are NOT here — they belong to separate domain servers, and
this server deliberately does not ship the `create-geometry`
skill that would teach them.

| Skill | Covers |
|-------|--------|
| query-filter | GetElements, WhereParam, WhereMatches, OrderByParam |
| aggregate-group | GroupByParam, SumParam |
| parameter-access | GetStr, GetNum, GetInt, GetVal, NativeProperties |
| write-modify | SetVal, SetNum, SetParam, Delete, Transact |
| display-visualize | Table, Select projection, Println, export_view |
| discovery-debug | CombinedParams, NativeProperties, ParamsDict |
| identity-orientation | FamilyName, Matches, GetElementType |
| materials-units | Materials, MaterialNames, InputUnit, OutputUnit |

## License

MIT
