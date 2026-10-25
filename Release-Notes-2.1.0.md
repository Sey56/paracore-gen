# Paracore-Gen v2.1.0

The generalist Revit MCP server, now built on the **shared MCP core**. Standalone installer; not
bundled with the add-in. Ships with **Paracore Add-in v4.8.1**.

## Highlights

- **8,393 lines lighter.** The eight REPL tools, the ten system-prompt sections, the nine shared
  method skills, the domain/skill registry and the gRPC client used to be a *copy* in this repo.
  They now live once, in `paracore/mcp/`, and this server imports them. One fix reaches all five
  MCPs — the same shape as the generic engine itself.

- **The drift is gone.** The copies had already diverged: this one read *"How many per type?"*
  where `model` and `gen` read *"per level"*. There is one text now, and a fix to it lands
  everywhere at once.

- **`export_view` can declare the caller's own posture.** It takes optional `execution_mode`
  (default `read_write`) and `license_tier`, so a caller that runs read-only can say
  `execution_mode="read_only"` instead of claiming a posture it does not have. This tool genuinely
  is safe under it — the read-only flag only gates the script-facing `Transact`, which `export_view`
  never touches.

- **The REPL IntelliSense client calls.** `grpc_client.py` gains the three RPCs behind completion,
  diagnostics and hover — the client half of the add-in's Roslyn workspace. This is plumbing for
  tools that want it, not a new tool.

- **`VERSION` is bundled into the exe from the build CLI**, not from the `.spec`. The spec is
  regenerated on every build, so a version written into it was one build away from being stale.

- **Proto stubs regenerated** from `protos/corescript.proto`, the single wire authority.

## No tool was added or removed

The tool set is unchanged, and `export_view`'s two new parameters are optional — an existing client
keeps working untouched.

## Building from source

The shared core is not vendored here. The build resolves it from a sibling `paracore` checkout
(`../paracore/mcp`), or from `PARACORE_MCP_CORE` if you set it. Its **skills and prompts are bundled
as data** under `mcp_core/…`, and `VERSION` must be added by the build CLI rather than the spec —
both are enforced in `build-gen.ps1`.

## Consent, reported rather than assumed

- **The agent learns what the operator chose.** Every execution result now carries
  `session_consent` — `granted`, `already_granted`, `denied` or `not_required` — so the tool output
  states who allowed the run instead of returning a bare success. A denial is terminal: the agent is
  told the operator blocked it, that nothing ran, and not to retry or work around it.

- **The session gate is read, not guessed.** `GetStatus` reports the session's consent
  (`unsettled` / `granted` / `denied`) over the new wire field 10, and this server asks before every
  agent call. The gate is per **Revit session**, not per server, so a session another MCP already
  had allowed is no longer mistaken for a fresh one — which used to make a long first call look like
  a consent dialog that was never going to appear.

- **A deadline that says which deadline it was.** A call made while the session is ungated is capped
  at **60 s**, because only a person can end that wait; once the gate is settled the call keeps its
  normal deadline. The error text names the cause rather than listing both, and the next call is
  cheap and definitive because the gate latches its answer.

## Requirements

**Paracore Add-in v4.8.1** installed and running in Revit — the two are released together.

⚠ **The consent-gate fix needs both halves.** The add-in asks with captions the watcher does not
recognise; the watcher is the one that must decline to answer. **Gen 2.1.0 against add-in 4.8.0 still
auto-approves**, because 4.8.0's dialog offers `OK` — a label the watcher presses on sight. Upgrade
the add-in as well, or the prompt stays decoration.
