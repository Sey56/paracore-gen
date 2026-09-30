# Revit MCP landscape — research and lessons

**Date:** 2026-09-30
**Purpose:** understand the field before building further. What has converged, what fails,
what we lead on, and what we are missing.
**Method:** public sources, read directly. Star counts and dates are as published; treat
them as indicative, not authoritative — this space moves weekly.

---

## 1. Who is actually out there

| Project | Stars / status | Arch | Tools | Notes |
|---|---|---|---|---|
| **revit-mcp/revit-mcp** | ~453, **archived Feb 2026** | TS + C# socket | 27 | The original. Had arbitrary C# execution + operation history. Dead; points at successor. |
| **mcp-servers-for-revit** | ~288, no commits since Apr 2026 | TS + C# socket | 20 | Successor. `send_code_to_revit`, module library, SQLite cache, `reset_model`. |
| **Autodesk Revit Public MCP Server** | Official, Tech Preview | Add-on + named pipe | ~38 across 3 tiers | Read / Write / Experimental tiers. Revit 2027 only. Ships with confirmation gates. |
| **HorizunGroup/horizun-revit-mcp** | Active, v1.3.3 (Sep 2026) | C# server + C# add-in | **123** (456 subops) | The most rigorous. Verified-write contract, dry-run, family authoring, release evidence. |
| **Sam-AEC/aec-model-bridge** | ~50, v1.1.0+ | Python hub + C# add-in | **100+** | Hub-and-spoke: Revit, Rhino, IfcOpenShell, Speckle (+Navisworks/Power BI pending). |
| **hungpixi/revit-mcp** | Active | Node + C# TCP :8080 | 35+ | `ExternalEvent` threading, Roslyn sandbox, Dynamo bridge, CAD→BIM. |
| **oakplank/RevitMCP** | ~53 | pyRevit + Python | — | Documents real API gaps (see §3.7). |
| **Demolinator/revit-mcp-server** | ~24, 84 commits | pyRevit | 48 | Revit 2024–2027. |
| **schauh11/revit-mcp-server** | ~20 | WPF panel in Revit + WebSocket | 53 | In-Revit chat panel. |
| **SzamosiMate/tapir-archicad-MCP** | ~93 | Python | **191+ auto-generated** | ArchiCAD. Dynamically generates tools from schemas + semantic `discover_tools`. |
| **Pilot AI (HMK)** | Commercial | Packaged | **340+ actions** | Revit + AutoCAD + Civil 3D + Navisworks, one installer, in-Revit chat. |
| **revitagents.com** | Commercial, early access | Governance layer | — | Not a server — policy/approval/audit on top of any Revit MCP. |

**Ecosystem context:** ~4,127 MCP servers and 28,000+ tools exist in total. AEC/design is one
of the more active verticals, but heavily skewed to *design* over *construction operations*.

### The strategic fact that matters most

**Autodesk now ships its own Revit MCP, with Write tools.** The widely-circulated comparison
sites still describe it as read-only 7 tools — that is out of date. The official help lists
three installable configurations (Read / Write / Experimental) spanning ~38 tools including
`modify_element_parameters`, `delete_elements`, `move_elements`, `rotate_elements`,
`create_sheet`, `create_schedule`, `create_plan_views`, `tag_elements`, and `export_*`.

This cuts both ways. It legitimises the category and normalises MCP for BIM teams. It also
means "we connect an LLM to Revit" is no longer a pitch. Autodesk's limits are real, though:
Revit **2027 only**, tied to their account and Assistant, and their own docs still say
*"Review the proposed changes before accepting them."*

---

## 2. What the field has converged on — these are now table stakes

1. **Dynamic code execution as an escape hatch.** `send_code_to_revit` (mcp-servers-for-revit,
   hungpixi), Roslyn sandbox, `execute_python`, `eval_ruby` (SketchUp), AutoLISP (AutoCAD).
   *Almost every capable server has one.* **Our dynamic C# REPL is no longer a differentiator.**
   It is the price of entry.
2. **Read-only vs read-write separation.**
3. **Transactions with auto-rollback on failure.**
4. **`ExternalEvent` marshalling** to Revit's single UI thread. Universal, for good reason.
5. **Human confirmation before destructive operations.** Autodesk: *"You are asked to confirm
   before deleting elements."* Confirmation is in the tool, not in the prompt.
6. **Tool consolidation beats tool sprawl.** `puran-water/autocad-mcp` exposes **8 tools covering
   many commands**; `multiCAD-mcp` exposes **56 commands in 7 tools**. The most-starred servers
   consolidate. (Horizun went the other way at 123 tools — but note they had to add
   *permission profiles* and *dispatch modes* to manage the blast radius.)
7. **Localhost-only transport.** Named pipes, loopback TCP, stdio. No network exposure.

---

## 3. Documented failure modes — the most valuable thing in this research

### 3.1 Deadlock from agent retry storms (the big one)

From the Axoworks analysis of Autodesk's own server:

> *"Rapid-fire or retry-loop queries from async LLM agents create a severe bottleneck that can
> deadlock the Autodesk pipe... If an agent issues multiple failing `query_model` calls, the
> server's internal query thread can become **permanently blocked** even though the pipe
> transport remains alive. Only a full restart clears it."*

Their diagnosis of the trigger:

> *"AnythingLLM's agent executor is **impatient** — it assumes failure after ~30s and initiates
> rapid-fire retries that flood the queue. This retry behaviour is **the primary trigger for
> deadlocks** and cannot be fully controlled via system prompt."*

**Why this matters to us directly.** Revit's API is single-threaded. Our own tool descriptions
say *"Self-correct up to 3 times"* and our REPL deadline is 120s. That is precisely the
pattern that deadlocks a queue. Our `ping` lies (§4.1), so an agent cannot distinguish a busy
Revit from a dead one — it will just retry. **We are currently shaped like the failure case.**

Their three mitigations, all worth copying:
- **Request deduplication** — coalesce duplicate retries in flight.
- **Heartbeat** — when a task nears client timeout, send *"Wait and do not retry."*
- **Pre-validation** — block broad/dangerous queries before they reach the main thread.

### 3.2 Silent empty results

Autodesk's `query_model` defaults `searchScope` to the **active view**. Omit `"AllViews"` and
you get empty results even with a fully loaded model. Documented as *"expected API behaviour,
not a bug."* Small models routinely omit the argument.

**We have the same class of problem.** Our own server instructions admit it: *"A mistyped name
returns empty — indistinguishable from 'no matches.'"* We partially mitigate with the schema
cache, but the failure is still silent by default.

### 3.3 Small models drop required arguments

Axotopia lists models verified stable and models that reliably fail; 7B–8B models *"often omit
required arguments or get stuck in infinite retry loops."* Reliability is model-dependent, and
this should be documented rather than discovered per-user.

### 3.4 Coordinate-system confusion

**Global Z (Internal Origin) vs Project Z (Project Base Point).** They built a *"Coordinate
Translation Layer"* explicitly *"to prevent LLM hallucination."* Our `InputUnit()` handles
units but says nothing about origin offsets. If a project has a non-zero base point, an agent
computing a placement will be confidently wrong.

### 3.5 LLM arithmetic

The stated design principle: *"custom tools bypass LLM math errors by executing local
deterministic calculations and use the LLM only for final narrative summaries."*

**We are already good here** — `.SumParam()`, `.GroupByParam("Level","Area","m2")` are
deterministic. This is an argument *for* our DSL, not against it.

### 3.6 Latency is real and must be designed around

Axotopia reports **30–60s+ for complex tasks** on Autodesk's server. Horizun added *durable
jobs* with IDs that survive a process restart, and a **bounded 16-slot FIFO queue with
cancellation**. Long operations must be addressable, not just awaited.

### 3.7 API gaps are real and worth recording

`oakplank/RevitMCP`: *"Revit exposes `ScheduleFieldType.Formula`, but does not expose a public
formula-string setter in this API version."* Horizun documents `BuiltInCategory` being
**Int32-backed in Revit 2023 and Int64-backed from 2024** — measured by reflection per year,
which caused a real bug (`Enum.IsDefined` with a boxed int threw, and the catch read it as
"no category").

**We should keep our own register.** These are exactly the things an agent will get wrong.

---

## 4. Best practices worth adopting

### 4.1 The verified-write contract (Horizun) — the single best idea in the field

**rehearse → apply → re-read**, with explicit elements:

- **Rehearsal / dry-run by default** for risky operations. Not a flag you remember — the default.
- **`dry_run` must be genuinely side-effect-free.** They shipped a bug where `dry_run=true`
  still rewrote a ledger and reported `verified_after_reread=true`. They now treat "dry run
  wrote something" as a P0 defect class.
- **Post-commit re-read** — re-read each requested value and compare.
- **`verify_changes`** — before/after snapshots from the *same camera*, with a red diff mapped
  back to the written elements. Reports overlaps, blocked doors, duplicates, MEP-through-structure.
- **`undo`** — undoes the last *verified batch*, and **refuses when the model or file changed
  since**. That refusal is the important part.

This is a stronger version of the preview/diff I proposed. Theirs adds the re-read *after*
commit and the refusal semantics on undo. Adopt the whole shape.

### 4.2 Plan execution with rollback (Horizun)

`execute_plan` composes **up to 100 typed actions** with dependencies and prior-result
references, wrapped in a **`TransactionGroup` rollback**. For a family build — create doc,
reference planes, forms, parameters, dimensions, load — this is exactly the right primitive.

### 4.3 Permission profiles, not regex scanning (Horizun)

They filter the **tool set** by profile: `safe_write` (70 tools), `full_write` (79),
`unsafe_code` (80, Python enabled), `core` (4). External-effect tools are simply *absent* from
`tools/list` under a safe profile.

Our equivalent is a regex blocklist over the submitted C# text (`_ANTI_PATTERNS`,
`_BLOCKED_ALWAYS`). That is weaker *and* it false-positives (D-MCP-2). A profile model that
decides which **capabilities** are reachable is both stronger and quieter.

### 4.4 Explicit unknown reporting (Horizun)

`horizun_code_check` returns **`not_decidable` with a reason** instead of guessing — e.g. travel
distance reported as a lower bound. Unloaded links and unsupported cases are reported
explicitly rather than approximated.

### 4.5 Reusable procedures — the thing we most lack

- mcp-servers-for-revit: `search_modules` / `use_module` — a **library of pre-tested code modules**.
- Horizun: `horizun_promote_script` — promotes a verified script to a named procedure
  *"so it stops being ad-hoc code."*
- Autodesk: `get_running_revit_instances`, `get_active_context` — small, always-available context.

**We have nothing here.** Every task in Paracore is ad-hoc code, regenerated and recompiled
each time. A procedure library is how the agent gets *faster* and *smaller* over time — which is
precisely the stated constraint.

### 4.6 Session cleanup

mcp-servers-for-revit ships `reset_model` — *"Clears intermediate model state created during AI
interactions."* An agent that creates things needs a way to find and remove what it created.
We have no such concept.

### 4.7 Provenance and idempotency (Horizun)

Created elements carry **source fingerprints and provenance**; CDE writes are **idempotent by
external key and read back after every write**. Worth borrowing for any bulk creation.

### 4.8 Context bloat management — independent confirmation of our approach

Horizun **reduced `tools/list` by ~64 KB without removing a single tool, argument, or
operation**, and serves the exact contract at a resource URI (`horizun://contract/tools/{tool}`).

Separately, the Grasshopper/MCP lecture describes **LangGraph "tool scope control"**: when a
server offers hundreds of tools, bind groups to nodes *"to avoid the LLM's attention
scattering."*

**Both arrived independently at what Paracore already does** — a small tool surface plus
lazily-read skill resources. That is strong validation, and it is worth saying so plainly.

### 4.9 Semantic tool discovery

- `tapir-archicad-MCP`: generates **191+ tools from schemas** and exposes `discover_tools`
  semantic search.
- `tekla_mcp_server`: MiniLM semantic mapping over 25+ tools.

The pattern: when the tool surface is large, add a *search* layer rather than loading everything.

---

## 5. Where Paracore already leads — protect these

| Strength | Why it matters | Field comparison |
|---|---|---|
| **A fluent domain DSL** — `GetElements("Walls").WhereParam("Fire Rating","2 hr").SetParam(...).Table()` | The agent writes *intent*, not plumbing. Fewer tokens, fewer failure modes, less accumulated error. | Nearly everyone else sends **raw C#/Python**. The Grasshopper work explicitly recommends a DSL as intermediate language to fight "translation loss" and "accumulated error". We already are one. |
| **Progressive-disclosure skills** (9 operation skills + catalog) | Small always-on surface, deep on demand. | Validated by Horizun's 64KB `tools/list` cut and LangGraph's tool-scope control. |
| **Schema cache for parameter discovery** | Attacks the #1 hallucination source — guessed parameter names. | Only `search_schema`-style lookups exist elsewhere; few cache it. |
| **5 consolidated tools** | Tool sprawl is the documented failure of 100-tool servers. | `puran-water` (8 tools) and `multiCAD` (7 tools → 56 commands) prove consolidation scales better. |
| **In-process gRPC** | Lower latency than TCP sockets or named pipes. | hungpixi uses TCP :8080; Autodesk uses named pipes. |
| **Session-persistent REPL variables** | Multi-step work without re-establishing state. | Most competitors are stateless per call. |
| **Anti-pattern compliance layer** | Nobody else rejects known-bad API usage before execution. | Unique. Needs sharpening, not removal. |

### And one thing the research settles outright

**No Revit MCP in the field models by driving the GUI.** Every capable server — including
Autodesk's own — uses the API. hungpixi's threading section explains why: direct socket-thread
writes cause *"immediate memory crashes"*, and everything must be marshalled through
`ExternalEvent` into Revit's own idle loop.

That is external confirmation of the earlier recommendation: **computer use belongs as a
camera, not a hand.** Reserve it for verification and for the UI-only corners (Family Editor
sketch mode, dialog-gated operations).

---

## 6. Where we are behind — the gap list

Ordered by value.

| # | Gap | Who does it | Cost to us |
|---|---|---|---|
| 1 | **Rehearse → apply → re-read**, with `dry_run` genuinely side-effect-free | Horizun | Medium (engine) |
| 2 | **Post-commit re-read verification** — prove the write landed | Horizun | Low |
| 3 | **Undo a verified batch, refusing if the model changed** | Horizun | Medium |
| 4 | **Reusable procedure library** (`search_modules` / `promote_script`) | mcp-servers-for-revit, Horizun | Medium |
| 5 | **Permission profiles** replacing regex scanning | Horizun | Low (Python) |
| 6 | **Retry-storm protection** — dedup, heartbeat, "do not retry" | Axotopia | **Low, and urgent** |
| 7 | **Bounded queue + cancellation + durable job IDs** | Horizun | Low (Python) |
| 8 | **Coordinate origin awareness** (base point vs internal origin) | Axotopia | Low |
| 9 | **Session cleanup** — find/remove what the agent created | mcp-servers-for-revit | Low |
| 10 | **Explicit `not_decidable` reporting** instead of guessing | Horizun | Low |
| 11 | **Visual verification** — highlighted before/after diff image | Horizun | Medium |
| 12 | **Version-drift handling** across Revit years | Horizun | Medium |
| 13 | **Provenance/fingerprint on created elements** | Horizun | Medium |
| 14 | **Plan execution with `TransactionGroup` rollback** | Horizun | Medium (engine) |
| 15 | **Local cache for offline analysis** | mcp-servers-for-revit | Low |
| 16 | **Multi-app bridge** (Rhino, Navisworks, Power BI) | Sam-AEC | Large — out of scope |

---

## 7. Strategic read

**The category is consolidating around two shapes.** Either a *large typed tool surface*
(Horizun 123, Sam-AEC 100+, Autodesk ~38, Pilot 340+) with permission profiles to manage the
blast radius, or a *small surface plus a code escape hatch* (mcp-servers-for-revit, hungpixi).

**Paracore is a third shape, and it is the better one:** a *small surface plus a high-level
domain DSL*, with code execution as the fallback rather than the primary interface. That is
what the Grasshopper research recommends and what the arithmetic-failure evidence supports.
It is also the only shape that satisfies "do not bloat the agent, it must work fast."

**But we are missing the envelope around writes.** The field has moved on from "can it write?"
to "can you prove what it wrote, and undo it if you can't?" We are still at "can it write?"

**And we are missing institutional memory.** Everyone else accumulates reusable operations;
we regenerate code every time. That is the single biggest lever on the stated speed
requirement, and it costs no context because procedures are loaded on demand.

### Revised priorities

The earlier plan's Track A/B/C/D ordering still holds, with these insertions:

- **Move retry-storm protection to the front.** It is cheap, it is Python-only, and we are
  currently shaped like the documented deadlock case. Dedup + heartbeat + an explicit
  "do not retry, Revit is busy" signal.
- **Reframe Track B3 (preview) as the full verified-write contract** — rehearse, apply,
  **re-read**, and report actual-vs-requested. The re-read is the part that makes it trustworthy.
- **Add a procedure library as its own track.** `search_procedures` / `run_procedure` /
  `promote_script`, backed by the existing skill-file mechanism. This is the answer to
  "must work fast" that also reduces context.
- **Replace the regex blocklist with permission profiles** — fixes D-MCP-2 as a side effect.
- **Add a small always-available context tool** (`get_context`) — Autodesk ships
  `get_active_context` and `get_running_revit_instances`; we ship nothing equivalent.

### What to deliberately not do

- Do not chase 100+ tools. The evidence says consolidation wins, and sprawl is the stated
  reason this project feels unmanageable.
- Do not build GUI-driving modelling. Nobody in the field does it, and the threading model
  explains why.
- Do not compete with Autodesk on their turf (Revit 2027 + Assistant). Compete on
  version breadth (2023–2027), client freedom (Claude, Cursor, anything MCP), the DSL, and
  parameter discovery.

---

## Sources

- Autodesk Revit MCP — tools and tiers: `help.autodesk.com/view/ADSKMCP/ENU/?guid=revitmcp_tools`
- Autodesk — handling unexpected results: `help.autodesk.com/view/ADSKMCP/ENU/?guid=ADSKMCP_CommonContent_handling_unexpected_results_html`
- Horizun Revit MCP: `github.com/HorizunGroup/horizun-revit-mcp`
- mcp-servers-for-revit tool reference: `deepwiki.com/mcp-servers-for-revit/revit-mcp/4-revit-tools-reference`
- hungpixi/revit-mcp: `github.com/hungpixi/revit-mcp`
- Axoworks logic engine (failure-mode analysis): `github.com/Axotopia/revitmcp`
- Revit Agents (governance): `revitagents.com`
- AEC Model Bridge: `mcpservers.org/zh-CN/servers/sam-aec/autodesk-revit-mcp-server`
- Survey of 30+ AEC MCP servers: `chatforest.com/reviews/construction-architecture-mcp-servers/`
- MCP options comparison: `hmktools.com/revit-mcp-comparison`
- LLM × Grasshopper (DSL as intermediate language): `autodesignlab.org/zh/blog/lecture-2025-rhino-mcp/`
