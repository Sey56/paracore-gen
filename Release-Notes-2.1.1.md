# Paracore-Gen v2.1.1

**The MCP server that generates REPL code for Revit. Ships the shared core from `paracore/mcp`.**

A small, targeted release: it stops the server from teaching things it cannot do, makes the build
prove it shipped its skills, and inherits the security and write-safety fixes made in the shared
core. Release with **Paracore Add-in v4.8.2** — install both together.

## What changed

### It no longer teaches modelling

`paracore-gen` generates REPL code against the raw Revit API, LINQ and the Paracore DSL. It does
not model — `paracore-model` is the server that does. `create-geometry` was still in this server's
skill catalogue, so the agent was being taught a workflow this server cannot support and pointed at
sibling servers it does not have.

It is now filtered out of **gen's** catalogue only. The skill stays in the shared core, because the
servers that model still use it. Eight method skills in this server, not nine.

### The build proves it shipped its skills

The bundler copies `mcp_core/skills` from the **working tree**, not from git, and a filter change
had left the bundle empty — an installer that shipped no skills at all, with no gate looking.
`build-gen.ps1` now runs `spikes/verify_bundled_skills.py` after every build and fails if the
bundle is empty or missing an expected skill. The same check covers prompts.

### A pick has no signal unless the agent supplies one

`pick_object` is not an agent tool, and the rules every session receives now say so outright instead
of leaving it to be discovered. It holds Revit's UI thread until the user clicks, and nothing it
prints reaches the chat before it returns — measured on the operator's screen: during a bare
`Pick()` he saw only the generic "Running …", which appears for every call. The status bar, its only
other cue, is invisible unless the pointer is already over Revit.

The guidance moved from this server's intro into the **shared** `COMMON_RULES`, so every domain gets
it, not just gen. It says what to do instead: **the user selects first** (`get_context` returns
`Selection`), or ask by name or parameter (`WhereMatches`, `WhereParam`).

⚠ `pick_object` is also no longer *omitted* here, because it no longer exists in any domain — it was
removed from the shared registry on 2026-10-28 (`paracore` `RETIRED.md` R11). Passing
`omit_common=("pick_object",)` had become a request to omit something already gone.

### Inherited from the shared core

Because this server imports `paracore/mcp` rather than carrying a copy, the fixes in Add-in v4.8.2
apply here without a line of gen-specific code:

- **A qualified type name no longer walks past the security scan.** `new System.Threading.Thread(`
  executed where `new Thread(` was refused. Fixed in all three lists — dangerous patterns, the
  read-only guard, the file/network policy — by blanking the namespace prefix before any rule runs.
- **The scans no longer read prose.** A comment mentioning `new Transaction(Doc)` refused a correct
  read-only query. Comments and string literals are blanked first.
- **A failed script is rolled back as a set**, and the reply says `THE MODEL MAY HAVE CHANGED` when
  a raw write ran outside any transaction.
- **A wrong parameter name raises** instead of returning `0`, and names the real parameter.

## Verification

The acceptance criterion for this release — one item, one test, one measured verdict — is
[`Docs/RELEASE_ACCEPTANCE.md`](Docs/RELEASE_ACCEPTANCE.md). Measured on the installed build:

| suite | result |
|---|---|
| tool surface (all eight tools, including error paths) | 27/27 |
| security scan, both layers | 51/51 |
| scan bypass — qualified names, prose, containment | 17/17 · frozen exe 8/8 |
| catalog search | 38/38 |
| engine regressions via the MCP | 25/25 |

⚠ **The scan criterion is now tested twice**: once in-process (the source is right) and once against
the frozen `.exe` (the artifact is right). They are different claims — a PyInstaller bundle is a copy,
and editing `tool_helpers.py` changes nothing in the exe until it is rebuilt.

## Requirements

- **Paracore Add-in v4.8.2** — released together; the core in this build expects it
- Windows x64
