## Paracore-Gen v2.1.1

Full notes: [Release-Notes-2.1.1.md](Release-Notes-2.1.1.md) · Previous: [v2.1.0](https://github.com/Sey56/paracore-gen/releases/tag/v2.1.0) · [v2.0.0](https://github.com/Sey56/paracore-gen/releases/tag/v2.0.0)

Install with **Paracore Add-in v4.8.2** — released together.

> **Since the last published release (v2.0.0).** v2.1.0 was tagged and held back; 2.1.1 supersedes it
> and contains everything it had — the shared core (8,393 lines that were five copies now live once),
> the `cap_exempt` table fix, the schema example that named a parameter walls do not have, the dead
> `build_prompt()` system prompt deleted, and the reflection-entry-point refusals. This note covers
> what 2.1.1 adds on top.

### It no longer teaches modelling

`paracore-gen` generates REPL code against the raw Revit API, LINQ and the Paracore DSL. It does not model — `paracore-model` is the server that does. `create-geometry` was still in **this** server's skill catalogue, so the agent was taught a workflow this server cannot support and pointed at sibling servers it does not have. It is now filtered out of gen's catalogue only; the skill stays in the shared core for the servers that model. **Eight method skills here, not nine.**

### The build proves it shipped its skills

The bundler copies `mcp_core/skills` from the **working tree**, not from git — and a filter change had left the bundle empty. An installer shipping no skills at all, with no gate looking. `build-gen.ps1` now runs `spikes/verify_bundled_skills.py` after every build and fails if the bundle is empty or missing an expected skill. Prompts are checked the same way.

### A pick has no signal unless the agent supplies one

`pick_object` is not an agent tool, and the rules every session receives now say so outright instead of leaving it to be discovered. It holds Revit's UI thread until the user clicks, and nothing it prints reaches the chat before it returns — measured on the operator's screen: during a bare `Pick()` he saw only the generic "Running …", which appears for every call. The status bar, its only other cue, is invisible unless the pointer is already over Revit.

The guidance moved from this server's intro into the **shared** `COMMON_RULES`, so every domain gets it, not just gen. It says what to do instead: **the user selects first** (`get_context` returns `Selection`), or ask by name or parameter (`WhereMatches`, `WhereParam`).

⚠ `pick_object` is no longer *omitted* here either, because it no longer exists in any domain — it was removed from the shared registry on 2026-10-28 (`paracore` `RETIRED.md` R11). Passing `omit_common=("pick_object",)` had become a request to omit something already gone.

### Inherited from the shared core (Add-in v4.8.2)

This server imports `paracore/mcp` rather than carrying a copy, so these apply here without a line of gen-specific code:

- **A qualified type name no longer walks past the security scan** — `new System.Threading.Thread(` executed where `new Thread(` was refused. Measured, then fixed in all three lists (dangerous patterns, read-only guard, file/network policy) by blanking the namespace prefix before any rule runs, so any pattern added later inherits it. `global::` covered too.
- **The scans no longer read prose** — a comment mentioning `new Transaction(Doc)` refused a correct read-only query. Comments and string literals are blanked first, in both layers. Fixing only the Python layer left the add-in refusing the same query one layer down; that is how the second half was found.
- **A failed script is rolled back as a set**, and the reply says `THE MODEL MAY HAVE CHANGED` when a raw write ran outside any transaction.
- **A wrong parameter name raises** instead of returning `0`, and names the real parameter.

### Verification

The acceptance criterion for this release — one item, one test, one measured verdict — is [`Docs/RELEASE_ACCEPTANCE.md`](Docs/RELEASE_ACCEPTANCE.md). Measured on the installed build:

| suite | result |
|---|---|
| tool surface (all eight tools, including error paths) | 27/27 |
| security scan, both layers | 51/51 |
| scan bypass — qualified names, prose, containment | 17/17 · frozen exe 8/8 |
| catalog search | 38/38 |
| engine regressions via the MCP | 25/25 |

⚠ The scan criterion is tested **twice**: in-process (the source is right) and against the frozen `.exe` (the artifact is right). A PyInstaller bundle is a copy — editing `tool_helpers.py` changes nothing in the exe until it is rebuilt.

### Requirements

- **Paracore Add-in v4.8.2** — released together
- Windows x64
