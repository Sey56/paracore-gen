# Paracore-Gen v2.0.0

The generalist Revit MCP server — previously released as **Paracore MCP v4.7.0**. Standalone
installer; not bundled with the add-in.

## Highlights

- **Renamed to Paracore-Gen.** The product was `Paracore-MCP`, briefly `Paracore-Core`; the remote
  repository was renamed to match. The name is on every surface — package, build script, installer
  and icon.

- **Three new tools**

  | Tool | What it is for |
  |---|---|
  | `get_context` | The current project, active view, selection and levels. Call it right after `ping`, so "the walls" or "this level" is not a guess. Read-only, no arguments. |
  | `pick_object` | Ask the user to click an element and get it back. ⚠ It **blocks** until they pick or press Escape — tell them to click in Revit. |
  | `export_view` | Render a Revit view to an image so the agent can *see* the model. `annotations`: `model` (default), `tags`, or `all`. |

- **A resident dialog watcher.** Revit reports most failures as a modal dialog on its UI thread, so
  a call that provokes one never returns. A daemon thread now answers the dialog from **outside**,
  pressing the button a human would. It never suppresses a failure and never touches a transaction.
  Kill switch: `PARACORE_WATCH_DIALOGS=0`.

- **`ping` now diagnoses three states.** gRPC alone cannot tell "Revit is closed" from "the server
  is toggled off" — both close the port. The reply now says which one you are in.

- **Robustness.** gRPC deadlines on `ExecuteRepl`; `single_flight(...)` allows exactly one in-flight
  Revit execution and **refuses, never queues**, a second — "REVIT IS BUSY — do not retry".

- **Skills and reference are generated from the shared authority**, so `SKILLS.md` and
  `EXTENSION_METHODS.md` cannot drift from the engine.

## Requirements

**Paracore Add-in v4.8.0** installed and running in Revit — the two are released together.
