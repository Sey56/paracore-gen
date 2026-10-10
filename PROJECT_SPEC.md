# PROJECT_SPEC.md — paracore-gen

## 0. ⚠⚠ READ THE MASTER SPEC FIRST

This repo is **one project in the Paracore ecosystem**. It is **not self-contained**, and it is
**not** the top authority.

Before changing anything here, read:

```
C:\Users\seyou\Paracore\paracore-ecosystem\MASTER_SYSTEM_SPEC.md
```

It lives **outside every project repo** — in the `paracore-ecosystem` repo, a **sibling** of this
one. The sections that bind this repo: **§3** (the artifact authority table), **§4** (the change
classes) and **"PRODUCT NAMING"** (the four naming surfaces).

⚠ **If that file is not present, STOP and ask for it. Do not infer the cross-project rules.**
⚠ This is a **pointer, not a copy** — the master's rules are deliberately not repeated here.

---

## 1. What this project is

The **generalist MCP server** — product name **`Paracore-Gen`**: it lets an AI drive Revit through
the engine's REPL. A separate product from the takeoff tool, and the **shared Python core** other
MCPs borrow from.

⚠ **Generalist, not a specialist.** Its job is to *generate and run a REPL script for any Revit
task*, not to be the deep expert on one. It teaches the nine Paracore **extension-method** skills
and may drop to the **raw Revit API, LINQ and .NET** when those methods are not enough. The deep
**modelling** and **family / conceptual-mass** recipes live in the sibling **`paracore-model`** and
**`paracore-family`** MCPs — this repo carries neither, and its `skills/` is exactly the nine
method skills.

⚠⚠ **The name is `paracore-gen` on EVERY surface** (renamed 2026-10-09, from `paracore-mcp`): the
repo, `build-gen.ps1`, `paracore-gen.iss`, the exe, the installer, `UninstallDisplayName`, the
`FastMCP(...)` handshake and the client's config key. There is no longer a product-name-vs-exe-name
split. The surfaces and the migration are pinned in the master spec's **"PRODUCT NAMING"**.

⚠ Other MCPs address this repo **by name, never by position** — `PARACORE_GEN_HOME` with an absolute
default. A hard-coded `..\..\..\paracore-gen` climb silently misses when a caller moves.
⚠ `PARACORE_MCP_HOME` is the **pre-rename name of the same variable**; callers still honour it as a
fallback so an environment that sets the old one keeps building. New callers set the new one.

## 2. Where things live

| Artifact | Path |
|---|---|
| Shared Python core | `mcp_core/` — `skills/*/SKILL.md`, `prompts/*.md` |
| Agent skills / prompts (authority) | `mcp_core/skills/`, `mcp_core/prompts/` |
| Engine API docs (**authority**) | `EXTENSION_METHODS.md`, `REPL_GUIDE.md` |
| Build | `build-gen.ps1` → `installers/` |

## 3. Invariants — this project must not break these

- ⚠ **The MCP exe is FROZEN. A source edit is INERT.** `mcp_core/skills/*.md` and
  `mcp_core/prompts/*.md` are bundled **inside** the exe — a change reaches nothing until you
  **rebuild → install → restart the client**.
- ⚠ **Never `grep` the exe's bytes to check content.** The archive is compressed, so present text
  returns 0 exactly like absent text.
- ⚠ A **missing `--add-data` ships a broken agent while the build reports success.** A source run
  looks fine; only the exe is broken.
- ⚠ **`paracore-gen.spec` is NOT used** — the build is driven by `--add-data` flags. Editing the spec
  is silently discarded. ⚠ It is also **generated**: the build writes it from `--name`, so a stale
  `paracore-mcp.spec` left over from the pre-rename build is dead weight, not a config file.
- ⚠ `EXTENSION_METHODS.md` and `REPL_GUIDE.md` here are the **authority**; other copies are
  generated. ⚠ **A generated copy is never edited — the next regeneration discards it.**
- ⚠ **`pytest` rotates and deletes `%TEMP%\pytest-of-<user>`** — a test run *is* a delete.

## 4. Not here

- No engine source. This repo is a **consumer** of the engine's public API.
- ⚠ **No specialist skills.** `skills/` is the nine generalist method skills only — no
  `project-modeling`, `annotations-dimensions`, `family-authoring` or `massing-forms`. Those belong
  to **`paracore-model`** / **`paracore-family`**; a copy here is drift.
- ⚠ Nothing in this file is private. Keep it that way: this repo may be public.
