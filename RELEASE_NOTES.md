## Paracore-Gen v2.1.0

Full notes: [Release-Notes-2.1.0.md](Release-Notes-2.1.0.md) · Previous: [v2.0.0](https://github.com/Sey56/paracore-gen/releases/tag/v2.0.0)

### Built on the shared core

- **8,393 lines lighter** — the eight REPL tools, ten prompt sections, nine skills, the domain registry and the gRPC client are now imported from `paracore/mcp/` instead of carried as a copy
- **The drift is gone** — the five copies had already diverged; there is one text now

### Tools

- **`export_view`** takes optional `execution_mode` (default `read_write`) and `license_tier`, so a read-only caller can declare its own posture
- **No tool was added or removed**

### Plumbing

- The three REPL IntelliSense client calls (completion, diagnostics, hover) are in `grpc_client.py`
- `VERSION` is bundled from the build CLI, not the `.spec`; proto stubs regenerated from `protos/corescript.proto`

### Requirements

- **Paracore Add-in v4.8.1** — released together
- ⚠ The consent-gate fix needs both halves: Gen 2.1.0 against add-in 4.8.0 still auto-approves the dialog, because 4.8.0's offers `OK`
