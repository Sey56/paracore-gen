# Paracore-Gen v2.1.3 — technical release notes

**The generalist MCP server for Revit — it writes REPL code and runs it; there is no separate run
step. Requires Paracore Add-in v4.8.4.**

An inherited-fixes release. This repo's own runtime code did not change behaviour: everything
functional comes from `paracore-mcp-core`, whose dialog handling, bulk-write advisory and sandbox
guidance were corrected. The generated engine reference is synced to Paracore 4.8.4's
one-rounding-rule change.

> **Supersedes the published v2.1.2 (2026-11-06).** Everything in
> [v2.1.2](https://github.com/Sey56/paracore-gen/blob/main/Release-Notes-2.1.2.md) is included,
> including the exe-provenance work (`CORE_VERSION` and `SOURCE_HASH`).
>
> **Complete inventory of all 10 commits in this repo: [§4](#4-complete-commit-inventory).** The
> shared core's 6 commits are inventoried in the
> [Paracore 4.8.4 technical notes](https://github.com/Sey56/Paracore/blob/main/Release-Notes-4.8.4.md#6-complete-commit-inventory).

## 1. Download

`Paracore-Gen-v2.1.3.exe` is attached to the **[Paracore v4.8.4 release
page](https://github.com/Sey56/Paracore/releases/tag/v4.8.4)** alongside the desktop app, the
Revit add-in and the VS Code extension — **one place for every installer**. The `v2.1.3` tag in
this repo carries a pointer release with **no assets**; it exists so this repo's "Latest" badge
does not keep pointing users at v2.1.2.

Install it alongside **Paracore Add-in v4.8.4** from that same page.

## 2. What changed in this repo

Nothing in the executable's behaviour. `mcp_server.py`, `build-gen.ps1` and `paracore-gen.iss`
changed only in comments — references to a private specification were removed from the public
repo, and the description of the generalist's skill catalogue was clarified. The README,
`PROJECT_SPEC.md`, `Docs/RELEASE_ACCEPTANCE.md` and older release notes were rewritten for the
public repo.

Two verification assets did change:

- **New `tests/test_dialog_watcher_gate.py`** pins the two silent halves of the watcher:
  `revit_call()` sets and clears the in-flight flag (including when the body throws), the gRPC stub
  call runs **inside** the gate over `ExecuteScript` (Forge does **not** use `ExecuteRepl`), a
  process with no resident watcher opens no gate, a record exists **while** `click()` is still
  confirming the close, `single_flight` never discards a late record, and two identical dialog
  instances produce two messages in the note.
- **`spikes/probe_bulk_warning.py`** was repaired and now covers the residual false positives. It
  used to point at the pre-2.1.2 core path and exited FATAL without testing anything; it now
  resolves both `paracore-mcp-core` (`mcp_core`) and `paracore/mcp` (`grpc_client`), re-execs into
  the build venv when `grpc` is absent, and adds the four residual false-positive cases plus a
  real-`foreach` must-warn case. 16/16 pass; the old detector fails all four new silent cases.

`EXTENSION_METHODS.md` and `REPL_GUIDE.md` were regenerated from the engine and are
**byte-identical** to `paracore`'s copies.

## 3. Inherited from the shared core (`paracore-mcp-core`)

This server imports `mcp_core` from `paracore-mcp-core` rather than carrying a copy, so these apply
without a line of gen-specific code. The shared core is tagged `release-4.8.4` at `c4b57f6`.

- **Bulk advisories only for a proven collection.** The old rule warned *unless* a receiver could
  be proven single, so any shape its allow-list missed (indexer, `foreach` variable, field,
  parameter, differently-typed assignment) was announced as a bulk write for exactly one element.
  `_receiver_kind` now returns single / collection / unknown and an advisory is emitted only for a
  proven collection; unknown receivers are silent. It is advisory only and never blocks.
- **No dialog note is lost.** Measured 2026-11-11: two "Insert conflicts with joined Wall" dialogs
  were answered but only the first reached the agent, because `_record()` published only after the
  up-to-1.2 s close confirmation and the next call destructively pre-drained the late record.
  `_record()` now publishes at **decision time** (by reference, so `closed`/`how` are visible
  mid-click) and `single_flight` never pre-drains — a late record is reported on the next call,
  labelled `late`. `_settle_dialogs()` waits up to 1 s only when a dialog was seen recently and
  nothing has been recorded, so an ordinary call pays no latency.
- **Two Revit failure channels, taught separately.** `COMMON_RULES` now distinguishes the
  **blocking modal** the watcher answers and reports from the **persistent (reviewable) warning**
  stored in the document and read with `Doc.GetWarnings()`, which can be non-blocking or appear
  with **no dialog at all**. It pins the baseline/delta recipe, counts **per description**, uses
  `GetFailingElements() -> e.Value`, says adjust-and-rerun until zero, and never suppresses a
  failure (no `IFailuresPreprocessor`).
- **A usable hint after a sandbox refusal.** `object.GetType().Name` resolves `.Name` through
  `System.Reflection.MemberInfo`, so the engine refuses it — but `check_dangerous_patterns` did
  not catch the source and the agent got a bare refusal. The hint now points at typed checks
  (`x is ModelLine ? "ModelLine" : ...`) and `ex.Message` and forbids reaching for reflection by
  another route. `suggest_for_error()` is exposed so a compile-only tool (Forge `validate_tool`,
  which returns the engine's raw result) gets the same guidance.
- **Skills synced to Paracore 4.8.4**: no accessor rounds unless `decimals` is passed;
  `GroupByParam` totals are raw sums.
- **Public-repo hygiene** in the shared core (README and `PROJECT_SPEC.md` rewritten as library
  documentation, private product names removed from docstrings). No code, symbol or behaviour
  changed.

## 4. Complete commit inventory

Baseline: `v2.1.2` = `e0b6334`. **10 commits.**

| commit | date | change |
|---|---|---|
| `a96e2ae` | 11-08 | Generated `EXTENSION_METHODS.md` synced with the engine's missing-parameter fix. |
| `d6e0b0c` | 11-08 | `spikes/probe_bulk_warning.py` repaired (both core paths, build venv, 4 residual cases + real-`foreach` must-warn). 16/16 pass. |
| `87ba572` | 11-08 | Tagline corrected: Paracore-Gen is a generator **and** executor — it writes REPL code and runs it in Revit with no separate run step. Historical 2.1.1 notes left as published history; the two published GitHub release bodies were corrected as text-only metadata. |
| `0299c64` | 11-09 | README rewritten around install, client config, tool list, build and doc links; drops the stale claim that `mcp_core` lives at `paracore/mcp/mcp_core`. |
| `99eb068` | 11-09 | README lead states the code-generation model (a C# script per request, no fixed task tools) and that the conversation happens in the MCP client the user prefers. |
| `464b677` | 11-09 | Private product names and an internal operator quote removed from `PROJECT_SPEC.md`, older release notes, `Docs/RELEASE_ACCEPTANCE.md`, installer/build comments and the server docstring. Corrects the claim that this server "cannot model" — what is filtered is a skill from the catalogue, not a capability. Comments and prose only; regenerated reference included. |
| `80c1316` | 11-11 | Generated mirror records that the missing-parameter raise stops at a pack assembly (paracore `12e321bb`): a compiled pack legitimately probes names whose absence is normal, so the engine keeps the older warn-and-return contract there, while a script still throws for a typo. |
| `35dc32d` | 11-12 | `EXTENSION_METHODS.md` and `REPL_GUIDE.md` regenerated for the one-rounding-rule engine change; byte-identical to `paracore`'s copies. |
| `144f7f4` | 11-12 | New `tests/test_dialog_watcher_gate.py` pins the `ExecuteScript` in-flight gate and the late-record read-back (see §2). |
| `7a27026` | 11-15 | Release commit: `Set-Version.ps1` writes `VERSION`, `pyproject.toml` and `uv.lock` to 2.1.3; manual surfaces — README, `RELEASE_NOTES.md`, this file. |

## 5. Related repositories (for building from source)

- **`paracore`** — the free engine, the Revit add-in, and the generated `EXTENSION_METHODS.md`
  surface that this server's skills are pinned to. Releases every installer, including this one.
- **`paracore-mcp-core`** — the shared MCP framework imported as `mcp_core`. It is a library, not
  an installer; nothing here is installed on its own.

`build-gen.ps1` expects these as sibling checkouts; override with `PARACORE_MCP_CORE` /
`PARACORE_WIRE_DIR` if they are elsewhere. ⚠ **Two** directories are needed: the shared core and
`paracore/mcp`, which still holds the wire contract (`grpc_client`, `corescript_pb2*`). A build
that sets only the core produces an exe with no core while reporting success.
`paracore/scripts/Set-Version.ps1` is never called from here.

## 6. Versioning and provenance

`paracore-gen` versions itself from its own root `VERSION` via its own `Set-Version.ps1`; this
release is **2.1.3**. `paracore` versions as one unit and is at **4.8.4**. `paracore-mcp-core`
has no version of its own; the exe records its identity as a `CORE_VERSION` short commit hash.

The frozen exe is a **copy**. A `.py` or `.md` edit is inert until rebuild + install + restart, so
`build-gen.ps1` re-bakes `CORE_VERSION` and `SOURCE_HASH` into `paracore-gen.exe` and runs the
bundled-skills / bundled-prompts checks after every build. Both values carry no timestamp, so a
byte-comparing gate does not go red on every rebuild. For this release
`CORE_VERSION = c4b57f6`, `SOURCE_HASH = 4b116d4123a07a08`. Installer ProductVersion and live
handshake results are measured on the installed build and reported in the published release body.

⚠ The `v4.7.0` tag in this repo is a legacy artifact from when this project was named
`paracore-mcp`. It is not on the 2.x line and does not represent a release of this server.

## 7. Verification

| check | result |
|---|---|
| `Set-Version.ps1 -Check` (`VERSION`, `pyproject.toml`, `uv.lock`) | all at 2.1.3 |
| `build-gen.ps1` | re-bakes `CORE_VERSION` + `SOURCE_HASH`; runs bundle checks |
| `EXTENSION_METHODS.md` / `REPL_GUIDE.md` vs `paracore` | byte-identical |
| installed `paracore-gen.exe` hash vs `dist/paracore-gen.exe` | match |
| `git diff --check` | clean |

`tests/test_dialog_watcher_gate.py` and `spikes/probe_bulk_warning.py` are source-tree assets; the
test suite has not been re-run for this release check (a pytest session rotates its temp directory).

## 8. Requirements

- **Paracore Add-in v4.8.4** — from the same release page
- Windows x64
