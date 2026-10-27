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
the deep specialist for modelling or families — those live in the sibling
`paracore-model` and `paracore-family` MCPs.

## What a snippet can reach

Agent code runs as C# inside Revit's own process, with `System` and `System.IO` already
imported. That is a real capability, so it is **refused at the boundary** rather than trusted:
`paracore-gen` scans every snippet before it is compiled, and the add-in scans it a second
time so a direct gRPC caller cannot skip the first check. The two lists are the same list, in
the same order — a test fails if they ever diverge.

⚠ **The consent dialog decides WHO may run agent code. It is a decision, not a second line of
defence** — do not read "the human clicked Allow" as protection. The scan is the protection.

**Refused outright — no agent snippet reaches these:**

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
- **Destroying, moving or replacing a file.** `File.Delete/Move/Replace/Copy/SetAttributes/
  OpenWrite/WriteAll*/Append*`, `Directory.Delete/Move`, `new StreamWriter(path)`, every
  `FileMode` except `CreateNew`, and the `FileInfo`/`DirectoryInfo` instance forms.
  Creating a **new** file is allowed — see below.
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
- **Files — create only.** Agent code may create a **new** file and may read files. It may
  **never replace, move or delete an existing one** — not even a file it wrote earlier in the
  same session. The blessed write is `FileMode.CreateNew`, which throws when the path exists;
  the agent then picks the next free name (`report.csv`, `report_001.csv`, …). Deleting files
  is the user's job.
  ⚠ That sentence is now **true of the code as well as the docs**: the delete/move/replace
  APIs above are refused by name, in both layers.
- **A human is not an agent.** A gallery tool or a REPL command *you* run keeps full file
  access — `RoomFinishUpdater` reads a CSV and writes one, and that is your action, not an
  agent's. The policy is keyed on the call's `source`, and only sources containing `agent`
  are held to it.

### Known limits, stated rather than implied

| Limit | What it means |
|---|---|
| It is a deny-list, not a sandbox | Every capability above is refused by name, and the entry points are refused rather than the target types — but a **delegate obtained from a framework method**, code hidden inside an **interpolated-string hole**, and a **loop inside a framework call** are not reasoned about. |
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
is `paracore/mcp/mcp_core`, imported as a package, so `paracore` and `paracore-gen`
must be **sibling checkouts** under one parent directory (override with
`PARACORE_MCP_CORE`).

Produces: `installers/Paracore-Gen-v2.1.0.exe`

## Install

1. Install the **Paracore Addin** from the [`paracore`](https://github.com/datadrivenconstruction/paracore) repo
2. Run `installers/Paracore-Gen-v2.1.0.exe`
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
(.rfa)** recipes are NOT here — they belong to the sibling `paracore-model` and
`paracore-family` MCPs, and this server deliberately does not ship the `create-geometry`
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
