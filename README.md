# Paracore-Gen

An MCP server that lets an AI assistant read and change an open Revit model. The assistant connects through Claude Desktop, Cursor, VS Code or any MCP client; Paracore-Gen talks to the Paracore Addin inside Revit over gRPC on `localhost:50051` and runs C# against the live project.

It has no fixed task tools. For each request the assistant generates a C# script and runs it against the live model, using Paracore's extension methods, LINQ or the raw Revit API as needed. The conversation happens in the client the user prefers — Claude Desktop, Cursor, VS Code or any MCP client.

It is an optional, separate installer. The desktop app and the REPL work without it.

## Install

1. Install the **Paracore Addin** from the [v4.8.3 release page](https://github.com/Sey56/Paracore/releases/tag/v4.8.3), open Revit and switch the Paracore server ON in the ribbon.
2. Run `Paracore-Gen-v2.1.2.exe` from the same release page. It installs `paracore-gen.exe` into `%APPDATA%\paracore-data\mcp-servers\`.
3. Add the server to your MCP client config, using `paracore-gen` as the key and the installed exe as `command`. No arguments are needed. Restart the client.

| Client | Config file |
|--------|-------------|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `.vscode/mcp.json` |

Ask the assistant to call `ping` to check the connection. Full config examples are in [Using Paracore-Gen](https://sey56.github.io/paracore-help/docs/ai-agent/using-paracore-gen/).

The server runs C# inside Revit. Revit asks for approval of agent code once per Revit session.

## Tools

| Tool | What it does |
|------|--------------|
| `ping` | Check the connection to Revit |
| `get_context` | Active view, current selection, project levels |
| `export_view` | Render a Revit view to an image |
| `_explore_revit_data` | Run C# to inspect the model; writes are discarded |
| `_execute_dynamic_query` | Run C# that changes the model, inside a transaction |
| `_search_schema` | Parameter schema for a Revit category |
| `_read_extension_methods` | Paracore extension-method reference |
| `get_globals` | Globals available to a snippet |
| `list_skills`, `read_skill` | Method guides for the assistant |

## Build from source

Requirements: Python 3.12, uv, Inno Setup 6, and sibling checkouts of `paracore` and `paracore-mcp-core` (override with `PARACORE_MCP_CORE` and `PARACORE_WIRE_DIR`).

```powershell
./build-gen.ps1
```

Produces `dist/paracore-gen.exe` and `installers/Paracore-Gen-v2.1.2.exe`.

## Documentation

- [Using Paracore-Gen](https://sey56.github.io/paracore-help/docs/ai-agent/using-paracore-gen/) — setup and everyday use
- [How Paracore-Gen works](https://sey56.github.io/paracore-help/docs/ai-agent/how-it-works/) — implementation and safety
- [REPL_GUIDE.md](REPL_GUIDE.md) and [EXTENSION_METHODS.md](EXTENSION_METHODS.md) — C# reference (generated copies; the authority is in `paracore/`)

## License

MIT
