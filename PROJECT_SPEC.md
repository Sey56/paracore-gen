# PROJECT_SPEC.md — paracore-mcp

## 0. ⚠⚠ READ THE MASTER SPEC FIRST

This repo is **one project in the Paracore ecosystem**. It is **not self-contained**, and it is
**not** the top authority.

Before changing anything here, read:

```
C:\Users\seyou\Paracore\paracore-ecosystem\MASTER_SYSTEM_SPEC.md
```

It lives **outside every project repo** — in the `paracore-ecosystem` repo, a **sibling** of this
one. The sections that bind this repo: **§3** (the artifact authority table) and **§4** (the change
classes).

⚠ **If that file is not present, STOP and ask for it. Do not infer the cross-project rules.**
⚠ This is a **pointer, not a copy** — the master's rules are deliberately not repeated here.

---

## 1. What this project is

The **generalist MCP server**: it lets an AI drive Revit through the engine's REPL. A separate
product from the takeoff tool, and the **shared Python core** other MCPs borrow from.

⚠ Other MCPs address this repo **by name, never by position** — `PARACORE_MCP_HOME` with an absolute
default. A hard-coded `..\..\..\paracore-mcp` climb silently misses when a caller moves.

## 2. Where things live

| Artifact | Path |
|---|---|
| Shared Python core | `mcp_core/` — `skills/*/SKILL.md`, `prompts/*.md` |
| Agent skills / prompts (authority) | `mcp_core/skills/`, `mcp_core/prompts/` |
| Engine API docs (**authority**) | `EXTENSION_METHODS.md`, `REPL_GUIDE.md` |
| Build | `build-mcp.ps1` → `installers/` |

## 3. Invariants — this project must not break these

- ⚠ **The MCP exe is FROZEN. A source edit is INERT.** `mcp_core/skills/*.md` and
  `mcp_core/prompts/*.md` are bundled **inside** the exe — a change reaches nothing until you
  **rebuild → install → restart the client**.
- ⚠ **Never `grep` the exe's bytes to check content.** The archive is compressed, so present text
  returns 0 exactly like absent text.
- ⚠ A **missing `--add-data` ships a broken agent while the build reports success.** A source run
  looks fine; only the exe is broken.
- ⚠ **`paracore-mcp.spec` is NOT used** — the build is driven by `--add-data` flags. Editing the spec
  is silently discarded.
- ⚠ `EXTENSION_METHODS.md` and `REPL_GUIDE.md` here are the **authority**; other copies are
  generated. ⚠ **A generated copy is never edited — the next regeneration discards it.**
- ⚠ **`pytest` rotates and deletes `%TEMP%\pytest-of-<user>`** — a test run *is* a delete.

## 4. Not here

- No engine source. This repo is a **consumer** of the engine's public API.
- ⚠ Nothing in this file is private. Keep it that way: this repo may be public.
