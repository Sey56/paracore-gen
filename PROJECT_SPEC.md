# PROJECT_SPEC.md — paracore-gen

## 0. Where the API authority lives

This server is a **consumer** of the engine's public API. The API's authority is
`EXTENSION_METHODS.md` and `REPL_GUIDE.md` in the public `paracore` repo; the copies in this
repo are generated. When a copy disagrees with the authority, fix the authority and regenerate.

---

## 1. What this project is

The **generalist MCP server** — product name **`Paracore-Gen`**: it lets an AI drive Revit through
the engine's REPL. It is built on the shared Python MCP framework published as
`paracore-mcp-core`.

⚠ **Generalist, not a specialist.** Its job is to *generate and run a REPL script for any Revit
task*; there is no fixed menu of operations, so the code for each request is written at that
moment. It serves the shared Paracore **extension-method** skills and may drop to the
**raw Revit API, LINQ and .NET** when those methods are not enough.

⚠⚠ **The name is `paracore-gen` on EVERY surface**: the repo, `build-gen.ps1`,
`paracore-gen.iss`, the exe, the installer, `UninstallDisplayName`, the `FastMCP(...)`
handshake and the client's config key. Change them together, never one at a time.

⚠ Other MCPs address this repo **by name, never by position** — `PARACORE_GEN_HOME` with an absolute
default. A hard-coded `..\..\..\paracore-gen` climb silently misses when a caller moves.
⚠ The pre-rename `PARACORE_MCP_HOME` fallback was **removed 2026-10-10** — set `PARACORE_GEN_HOME`.

## 2. Where things live

| Artifact | Path |
|---|---|
| Shared Python core | ⚠⚠ **NOT in this repo — `paracore-mcp-core/mcp_core/`** (a SIBLING, imported as a package since 2026-10-13). It provides `tools.py`, `summarizer.py`, `schema_cache.py`, `prompt_assembler.py`, `metrics.py`, `dialog_watcher.py`, the nine shared `skills/*/SKILL.md` and `prompts/*.md`. There is **no** `paracore-gen/mcp_core/` any more |
| ⚠ **The wire contract** | **Stays in `paracore/mcp/`** — `grpc_client.py`, `utils.py`, `corescript_pb2*.py`, beside the `protos/corescript.proto` that generates them. `mcp_core` imports `grpc_client` in five places, so a build needs **TWO** paths: `$SharedCore` (the core repo) and `$WireDir` (`paracore/mcp`). ⚠ A build that sets only the first produces an exe with NO core while reporting success |
| Agent skills / prompts (authority) | ⚠ **`paracore-mcp-core/mcp_core/skills/` and `.../prompts/`** — ONE copy, shared by every MCP. ⚠ This repo declares **no** domain skills of its own (its catalogue is the shared nine) and has **no** local `skills/` or `prompts/` directory |
| Engine API docs (**GENERATED copies** — authority is `paracore/`) | `EXTENSION_METHODS.md`, `REPL_GUIDE.md` |
| Build | `build-gen.ps1` → `installers/` |

## 3. Invariants — this project must not break these

- ⚠ **The MCP exe is FROZEN. A source edit is INERT.** `mcp_core/skills/*.md` and
  `mcp_core/prompts/*.md` — which live ONCE in `paracore-mcp-core/mcp_core/` — are bundled **inside**
  the exe, so an edit there reaches nothing until you
  **rebuild → install → restart the client**.
- ⚠ **Never `grep` the exe's bytes to check content.** The archive is compressed, so present text
  returns 0 exactly like absent text.
- ⚠ A **missing `--add-data` ships a broken agent while the build reports success.** A source run
  looks fine; only the exe is broken.
- ⚠ **`paracore-gen.spec` is NOT used** — the build is driven by `--add-data` flags. Editing the spec
  is silently discarded. ⚠ It is also **generated**: the build writes it from `--name`, so a stale
  `paracore-mcp.spec` left over from the pre-rename build is dead weight, not a config file.
- ⚠ `EXTENSION_METHODS.md` and `REPL_GUIDE.md` here are **GENERATED COPIES**; the authority is
  **`paracore/`** (moved 2026-10-13 — these docs describe the engine, which lives there).
  ⚠ **A generated copy is never edited — the next regeneration discards it.**
- ⚠ **`pytest` rotates and deletes `%TEMP%\pytest-of-<user>`** — a test run *is* a delete.

## 4. Not here

- No engine source. This repo is a **consumer** of the engine's public API.
- ⚠ **No specialist skills.** This server declares no domain skills of its own — no
  `project-modeling`, `annotations-dimensions`, `family-authoring` or `massing-forms`.
  A copy here is drift.
- ⚠ Nothing in this file is private. Keep it that way: **this repo is PUBLIC**.
