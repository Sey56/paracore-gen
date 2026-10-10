## Paracore-Gen v2.0.0

The generalist Revit MCP server — previously released as **Paracore MCP v4.7.0**. Standalone
installer; not bundled with the add-in.

### Renamed

The product was `Paracore-MCP`, briefly `Paracore-Core`, and is now **Paracore-Gen**; the remote
repository was renamed to match. The name is on every surface:

- package name `paracore-agent` → `paracore-gen`
- `build-mcp.ps1` → `build-gen.ps1`
- `paracore-mcp.iss` → `paracore-gen.iss`
- `icons/paracore-mcp.ico` → `icons/paracore-gen.ico`

### New tools

| Tool | What it is for |
|---|---|
| `get_context` | The current project, active view, current selection and levels. Call it right after `ping` — without it, "the walls" or "this level" in a request is a guess. Read-only, no arguments. |
| `pick_object` | Ask the user to click an element and get it back — for "this wall", "the column I have open". Optional `selection_type` (`Element` / `Face` / `Edge`) and `category_filter`. ⚠ It **blocks** until the user picks or presses Escape, so the user must be told to click in Revit. |
| `export_view` | Render a Revit view to an image so the agent can *see* the model. `view_name` (omit for the active view), `pixel_size` (default 1200), and `annotations`: `model` (default — hide all annotation), `tags` (keep dimensions and tags, hide datum marks), or `all`. |

`ping` also grew a three-state diagnosis. gRPC alone cannot tell "Revit is closed" from "the in-Revit
server is toggled off" — both close port 50051 — so a Revit process check supplies the missing
signal, and the reply now says which of the three states you are in.

### A resident dialog watcher

Revit reports most failures as a modal dialog on its UI thread — and a tool call runs C# on that
same thread, so a call that provokes a dialog never returns and the client eventually times out.
`mcp_core/dialog_watcher.py` is a daemon thread started at server boot that answers the dialog from
**outside**, and the root `grpc_client.py` opens an in-flight gate around the round trip so the
watcher only acts while a call is genuinely waiting. A named mutex elects one actor across all
running Paracore MCP servers, so two of them cannot answer the same dialog twice. It never suppresses
a failure and never touches a transaction — it presses the button a human would.
Kill switch: `PARACORE_WATCH_DIALOGS=0`.

### Skills and reference

- The nine operation-based skills are unchanged in kind; `create-geometry`, `display-visualize` and
  `identity-orientation` gained material.
- `SKILLS.md` and `EXTENSION_METHODS.md` are now **generated from the shared authority**, so they
  cannot drift from the engine.
- `mcp_core/shared_skills.py` is new: the shared skill registry.
- `PROJECT_SPEC.md` is new — the repo contract.

### Robustness

- gRPC deadline and timeout on `ExecuteRepl`.
- `single_flight(...)` allows exactly one in-flight Revit execution and **refuses, never queues**, a
  second — Revit's API is single-threaded, so a retry would queue behind the running call and
  repeated retries can wedge Revit. The refusal is explicit: "REVIT IS BUSY — do not retry".
- Compliance is split in two: `check_paracore_compliance(...)` **blocks** a security or compliance
  anti-pattern, while `lint_paracore_conventions(...)` only **advises** and never blocks a call.
- `mcp_core/summarizer.py`, `tool_helpers.py` and `tools.py` reworked; the summarizer now has its
  own tests (`tests/test_summarizer.py`, `tests/test_summarizer_teeth.py`).

### Requirements

**Paracore Add-in v4.8.0** installed and running in Revit — the two are released together.
