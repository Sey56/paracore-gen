# Paracore-Gen v2.1.2

**The MCP server that generates REPL code for Revit. Requires Paracore Add-in v4.8.3.**

A provenance and correctness release. The frozen exe can now be **asked** which shared core and
which source tree it was built from, instead of being guessed from an mtime. It also inherits the
security and Revit 2027 work shipped in the shared core with Add-in v4.8.3.

Release with **Paracore Add-in v4.8.3** — install both together.

> **Supersedes the published v2.1.1 (2026-10-29).** Everything in
> [v2.1.1](Release-Notes-2.1.1.md) is included. This note covers the 8 commits since that tag.

## What changed in this repo

### The shared core is resolved from its own repo

`paracore-mcp-core` was split out of the free engine repo into its own MIT repo. `build-gen.ps1`
used to look for the core at the pre-move single path; it now resolves **the two sibling checkouts**.
`mcp_server.py` and the probes/tests were updated to match. A consumer's build must never dirty
the core, so generated identity files are written into this repo's build dir, not into the core.

### The exe carries its own provenance

Two values are baked into the frozen exe **as data**, with no timestamp (a byte-comparing gate
would otherwise go red on every rebuild for no reason):

- **`CORE_VERSION`** — the identity of the shared core inside this exe. The exe can be asked which core it contains instead of the answer being inferred from an mtime.
- **`SOURCE_HASH`** — a hash of this repo's **tracked** `.py` files, so the exe check can detect edits to `mcp_server.py`, `forge_core/` and the rest that a core pin and asset checks are blind to. Throwaway files are excluded.

This matters because an MCP is a **frozen exe**: a `.py` or `.md` edit is inert until rebuild +
install + restart. The hash turns that from a thing to remember into a thing the gate can prove.

### The spec and the docs say what is true

- `PROJECT_SPEC.md` now says this repo is **PUBLIC (MIT)**, not "may be public".
- `EXTENSION_METHODS.md` is synced from the engine, including `ScriptApi.Files`.
- The README now says what the security scan **actually is** and pins the page to the code, backed by a new `tests/test_scan_coverage.py` suite and probes for native properties, transaction granularity and append diagnostics.
- The parameter-ownership REPL probe is kept, and the engine-regression probe uses `ElementId.Value` rather than the `IntegerValue` that Revit 2027 removed.

## Inherited from the shared core (Add-in v4.8.3)

This server imports `paracore/mcp` rather than carrying a copy, so these apply without a line of
gen-specific code:

- **Dangerous machine capabilities are refused at compile time**, and file access is confined to one workspace.
- **Scan bypasses are closed** in the add-in's instance-form layer, and a refused script no longer hands out the recipe it was refused for.
- **Qualified type names no longer walk past the security scan** (`new System.Threading.Thread(` where `new Thread(` was refused), and the scans no longer read comments or string literals as prose.
- **Revit 2027 works.** One `net8.0-windows` payload, a shim-level `Default.Resolving` guard that stops a second `CoreScript.Engine.dll` loading into `Default`, and the moved 2027 all-users `.addin` path. No .NET 10 retarget.

## Versioning

Each sibling MCP versions itself from its own root `VERSION` via its own `Set-Version.ps1`.
`paracore-gen` is **2.1.2**; `paracore-model`, `-family`, `-forge` and `-takeoff` stay at **2.0.0**.
The `paracore` engine + add-in + desktop + VS Code extension version as one unit and are at
**4.8.3** — `paracore/scripts/Set-Version.ps1` is never called from here.

⚠ The `v4.7.0` tag in this repo is a legacy artifact from when this project was named
`paracore-mcp`. It is not on the 2.x line and does not represent a release of this server.

## Verification

| check | result |
|---|---|
| `Set-Version.ps1 -Check` (`VERSION`, `pyproject.toml`, `uv.lock`) | all at 2.1.2 |
| `build-gen.ps1` | bakes `CORE_VERSION` + `SOURCE_HASH` into the exe |
| engine-regression probe | uses `ElementId.Value` (Revit 2027) |

⚠ A version bump alone does **not** produce a shippable exe: `build-gen.ps1` must be re-run so
the `2.1.2` product version and the fresh source hash are baked into the frozen binary.

## Requirements

- **Paracore Add-in v4.8.3** — released together; the shared core in this build expects it
- Windows x64
