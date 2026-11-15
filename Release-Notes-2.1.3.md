# Paracore-Gen v2.1.3

**The generalist MCP server for Revit — it writes REPL code and runs it; there is no separate run
step. Requires Paracore Add-in v4.8.4.**

An inherited-fixes release. This repo's own runtime code did not change behaviour: everything
functional comes from `paracore-mcp-core`, whose dialog handling, bulk-write advisory and sandbox
guidance were corrected. The generated engine reference is synced to Paracore 4.8.4's
one-rounding-rule change.

> **Supersedes the published v2.1.2 (2026-11-06).** Everything in
> [v2.1.2](https://github.com/Sey56/paracore-gen/blob/main/Release-Notes-2.1.2.md) is included,
> including the exe-provenance work (`CORE_VERSION` and `SOURCE_HASH`).

## Download

`Paracore-Gen-v2.1.3.exe` is attached to the **[Paracore v4.8.4 release
page](https://github.com/Sey56/Paracore/releases/tag/v4.8.4)** alongside the desktop app, the
Revit add-in and the VS Code extension — **one place for every installer**. The `v2.1.3` tag in
this repo carries a pointer release with **no assets**; it exists so this repo's "Latest" badge
does not keep pointing users at v2.1.2.

Install it alongside **Paracore Add-in v4.8.4** from that same page.

## What changed in this repo

Nothing in the executable's behaviour. `mcp_server.py`, `build-gen.ps1` and `paracore-gen.iss`
changed only in comments — references to a private specification were removed from the public
repo, and the description of the generalist's skill catalogue was clarified. The README,
`PROJECT_SPEC.md`, `Docs/RELEASE_ACCEPTANCE.md` and older release notes were rewritten for the
public repo.

Two verification assets did change:

- **New `tests/test_dialog_watcher_gate.py`** pins the two silent halves of the watcher:
  `revit_call()` sets and clears the in-flight flag (including when the body throws),
  `execute_repl` performs the gRPC call *inside* the gate, and `mcp_server.py` still starts the
  watcher from `__main__`.
- **`spikes/probe_bulk_warning.py`** was repaired and now covers the residual false positives.

`EXTENSION_METHODS.md` and `REPL_GUIDE.md` were regenerated from the engine and are
**byte-identical** to `paracore`'s copies.

## Inherited from the shared core (`paracore-mcp-core`)

This server imports `mcp_core` from `paracore-mcp-core` rather than carrying a copy, so these apply
without a line of gen-specific code:

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
- **Skills synced to Paracore 4.8.4**: no accessor rounds unless `decimals` is passed.

## Related repositories (for building from source)

- **`paracore`** — the free engine, the Revit add-in, and the generated `EXTENSION_METHODS.md`
  surface that this server's skills are pinned to. Releases every installer, including this one.
- **`paracore-mcp-core`** — the shared MCP framework imported as `mcp_core`. It is a library, not
  an installer; nothing here is installed on its own.

`build-gen.ps1` expects these as sibling checkouts; override with `PARACORE_MCP_CORE` /
`PARACORE_WIRE_DIR` if they are elsewhere. ⚠ **Two** directories are needed: the shared core and
`paracore/mcp`, which still holds the wire contract (`grpc_client`, `corescript_pb2*`). A build
that sets only the core produces an exe with no core while reporting success.
`paracore/scripts/Set-Version.ps1` is never called from here.

## Versioning

`paracore-gen` versions itself from its own root `VERSION` via its own `Set-Version.ps1`; this
release is **2.1.3**. `paracore` versions as one unit and is at **4.8.4**. `paracore-mcp-core`
has no version of its own; the exe records its identity as a `CORE_VERSION` short commit hash.

⚠ The `v4.7.0` tag in this repo is a legacy artifact from when this project was named
`paracore-mcp`. It is not on the 2.x line and does not represent a release of this server.

## Verification

The frozen exe is a **copy**. A `.py` or `.md` edit is inert until rebuild + install + restart, so
`build-gen.ps1` re-bakes `CORE_VERSION` and `SOURCE_HASH` into `paracore-gen.exe` and runs the
bundled-skills / bundled-prompts checks after every build. Installer ProductVersion and live
handshake results are measured on the installed build and reported in the published release body.

| check | result |
|---|---|
| `Set-Version.ps1 -Check` (`VERSION`, `pyproject.toml`, `uv.lock`) | all at 2.1.3 |
| `build-gen.ps1` | re-bakes `CORE_VERSION` + `SOURCE_HASH`; runs bundle checks |
| `EXTENSION_METHODS.md` / `REPL_GUIDE.md` vs `paracore` | byte-identical |
| `git diff --check` | clean |

## Requirements

- **Paracore Add-in v4.8.4** — from the same release page
- Windows x64
