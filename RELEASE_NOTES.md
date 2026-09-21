## Paracore MCP v4.7.0

The generalist MCP server for Paracore — now a standalone installer, previously bundled inside the Revit addin.

### Tools

- `ping` — verify connection to Revit
- `explore_revit_data` — run read-only C# for model discovery
- `execute_dynamic_query` — run read-write C# with auto-transaction
- `search_schema` — fast parameter lookup per Revit category

### What's New

- First standalone release (extracted from the addin installer)
- `GetStr("Level")` works on every category — Walls, Beams, Columns, Doors
- Nine operation-based skills replace the monolithic extension methods catalog
- Unknown parameter diagnostic warning with CombinedParams discovery hint
- Debug loops allowed (relaxed foreach+Println pattern matching)

### Requirements

Paracore Addin v4.7.0 installed and running in Revit.
