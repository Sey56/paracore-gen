# Paracore-Gen

The generalist Model Context Protocol server for Paracore — enables Claude Desktop,
Cursor, VS Code, and any MCP-compatible client to explore and control Revit through
natural language.

⚠ The product is **`Paracore-Gen`** on every surface (renamed 2026-10-09, from
`Paracore-MCP`): repo, build script, exe, installer, `UninstallDisplayName`, the
`FastMCP(...)` handshake and the client's config key. See
`paracore-ecosystem/MASTER_SYSTEM_SPEC.md` → **"PRODUCT NAMING"**.

## What it does

Connects to the Paracore Addin running in Revit (via gRPC on `localhost:50051`)
and provides MCP tools for running C# code dynamically:

- **`ping`** — verify connection to Revit
- **`get_context`** — active view, current selection, project levels
- **`pick_object`** — let the user pick an element in Revit
- **`export_view`** — render a Revit view to an image so the agent can SEE the model
- **`_explore_revit_data`** — run read-only C# for discovery (never modifies the model)
- **`_execute_dynamic_query`** — run read-write C# with auto-transaction wrapping
- **`_search_schema`** — fast parameter schema lookup per Revit category
- **`_read_extension_methods`** — the full Paracore extension methods catalog

⚠ This is the **generalist** server: it generates and runs a REPL script for *any*
Revit task. It prefers the Paracore extension methods, but the **raw Revit API, LINQ
and .NET** are all in scope when the methods are not enough. It is deliberately not
the deep specialist for modelling or families — those live in the sibling
`paracore-model` and `paracore-family` MCPs.

## Build

```powershell
./build-gen.ps1
```

Requirements: Python 3.12, Inno Setup 6.

Produces: `installers/Paracore-Gen-v4.7.0.exe`

## Install

1. Install the **Paracore Addin** from the [`paracore`](https://github.com/datadrivenconstruction/paracore) repo
2. Run `installers/Paracore-Gen-v4.7.0.exe`
3. Configure Claude Desktop to use the MCP server

## Structure

```
mcp_core/           Shared foundation — tools, validation, summarizer, gRPC client
  skills/           9 operation-based skill resources (query-filter, write-modify, etc.)
  prompts/          Composable system prompt
mcp_server.py       MCP server — stdio entry point
grpc_client.py      gRPC communication with the Paracore Addin
```

## Skills

Nine operation-based skills replace the monolithic extension methods catalog. Each
skill is a focused `SKILL.md` resource. Claude Desktop discovers them automatically.

⚠ These cover the Paracore **extension methods**. Deep **modelling** and **family
(.rfa)** recipes are NOT here — they belong to the sibling `paracore-model` and
`paracore-family` MCPs.

| Skill | Covers |
|-------|--------|
| query-filter | GetElements, WhereParam, WhereMatches, OrderByParam |
| aggregate-group | GroupByParam, SumParam |
| parameter-access | GetStr, GetNum, GetInt, GetVal, NativeProperties |
| write-modify | SetVal, SetNum, SetParam, Delete, Transact |
| display-visualize | Table, Select projection, Println, export_view |
| discovery-debug | CombinedParams, NativeProperties, ParamsDict |
| create-geometry | Wall.Create, Floor.Create, FamilyInstance placement |
| identity-orientation | FamilyName, Matches, GetElementType |
| materials-units | Materials, MaterialNames, InputUnit, OutputUnit |

## License

MIT
