# RELEASE ACCEPTANCE — `paracore` (engine + add-in) and `paracore-gen` (MCP)

**What this file is:** the release criterion. It is written BEFORE a test round and it is not
edited during one. It names every capability we intend to ship, the test that proves it, and
the measured verdict.

**What this file is not:** a test log, a bug tracker, or a wish list. A finding that is not an
`A<n>` item belongs in §5, and §5 does not block a release.

---

## 0. The loop this ends

Testing ran for roughly a week and every round produced a new bug. That is not bad luck, and it
is not a sign the product is bad. It is what happens when **"done" is never defined**: every
finding is weighed against an infinite bar, so the bar is never met.

Three mechanisms produced the loop, all visible in the record:

1. **A test suite that grows with each finding cannot terminate.** Each round added probes, each
   probe found something, so the total never converged. The number of things to test was
   unbounded because nothing said which things mattered.
2. **A probe defect and a product defect were reported in the same voice.** A truncated snapshot,
   an inverted assertion, and a genuinely unreachable guard all read as "found a bug". That made
   a working product sound broken and made the real defects hard to rank.
3. **A bug found late always looks more important than a bug found early**, because it is the one
   in front of you. Without a fixed list there is no way to say "that is outside what we
   promised, it ships as a backlog item".

The escape is not more testing and it is not a lower bar. It is **a fixed list of promises, each
with one test, agreed before the round starts.**

## 1. The rule

1. **The criterion below is fixed.** An `A` item is added only for a capability we intend to
   claim in the release notes. It is never added to cover something a test happened to find.
2. **Release condition:** every `A` item PASSES on the installed build, and no open Sev-1 or
   Sev-2 defect exists (§4). Nothing else.
3. **A defect inside an `A` item is a blocker.** The capability is either **fixed** or **cut**.
   A capability that is cut is removed from the product surface, not shipped behind a
   disclaimer — a feature that does not work has no place in a release.
4. **A defect outside every `A` item is a backlog ticket.** It is written down and it does not
   block. This is the whole point: it gives a real answer to "we found one more thing".
5. **The release notes are the PASS rows of §3.** Nothing may be claimed in the release that is
   not a green row here. This is what stops the notes from describing the intent instead of the
   artifact.
6. **A round that changes the product re-runs every `A` item**, not only the affected one. A
   green row from a previous build is not evidence about this build (see RULE 25: a snapshot is
   not a fact).

## 2. Scope

| artifact | what it is | in this release |
|---|---|---|
| `paracore` engine + add-in | the CoreScript runtime, the REPL, the write-safety envelope | **yes** |
| `paracore-gen` MCP | the generalist tool surface an agent drives Revit through | **yes** |
| `paracore-model` / `-family` / `-forge` / `-takeoff` MCP | four sibling exes | **no** — operator decision: *"only i use them for now. they have their own time to be adjusted"* |

`paracore-gen` is the only consumer being released, so it is the only consumer tested. A defect
that exists only in a sibling is out of scope by decision, not by oversight — and the `mcp-exes`
gate will report those four as stale for exactly that reason.

## 3. The criterion

Status is measured on the installed build named in §3.1. `A` = the probe that proves it.

### A. Install and liveness — *the thing runs*

| # | the promise | test | status |
|---|---|---|---|
| A1 | The add-in loads and the installed engine DLL is the one that was built | `installed-addin` gate (mtime + hash) | PASS |
| A2 | The MCP exe starts, completes the stdio handshake, and lists its tools | `probe_exe_release` (5/5) | PASS |
| A3 | The frozen exe carries its skills and prompts — no empty bundle | `verify_bundled_skills` / `verify_bundled_prompts` | PASS |
| A4 | The engine and the MCP answer a liveness call | `ping`, `get_context` | PASS |

### B. Execution — *code runs and the answer is about the user's code*

| # | the promise | test | status |
|---|---|---|---|
| A5 | A snippet executes and its output comes back | `probe_installed_exe` | PASS |
| A6 | REPL variables persist across submissions in one session | `probe_rewriter_live`, `__safeSnap` persistence | PASS |
| A7 | A compile error names the line **the user** wrote, not the injected wrapper | `probe_rewriter_live` (10/10) | PASS |
| A8 | The source rewriter does not change the meaning of valid code | `probe_rewriter_live` (10/10) | PASS |
| A9 | The engine's documented method surface behaves as documented | `probe_engine_regressions` (25/25) | PASS |

### C. Write safety — *a failed script does not half-apply*

| # | the promise | test | status |
|---|---|---|---|
| A10 | A script that writes and then throws is **rolled back as a set** | `verify_rollback_live` (9/9) | PASS |
| A11 | The reply says **what really happened**, including "the model may have changed" when a raw write ran outside any transaction | `verify_rollback_live` (9/9) — asserts the honest sentence is present AND the false all-clear is absent | PASS |
| A12 | A failed write names the line that failed | `verify_rollback_live` (9/9) | PASS |
| A13 | A bulk write warns that it costs N undo entries before it commits | `probe_bulk_warning` (11/11) | PASS |
| A14 | A type-level write reports the advisory for the type it actually touched | `probe_type_write_advisory` (9/9) | PASS |
| A15 | `explore_revit_data` refuses a model write, and any write that reaches it anyway is discarded | `probe_scan_bypass` containment case | PASS |

### D. Data access — *the agent can find things*

| # | the promise | test | status |
|---|---|---|---|
| A16 | Element queries, filters and counts return the model's real contents | `probe_write_safety` (609-wall snapshot, 0 drift) | PASS |
| A17 | Catalog search finds a method by name and by intent | `probe_catalog_search` (38/38) | PASS |
| A18 | Schema search, globals and the extension-method catalog answer correctly | `probe_tool_surface` (27/27) | PASS |

### E. Tool surface — *every tool we advertise actually works*

| # | the promise | test | status |
|---|---|---|---|
| A19 | All eight tools are callable and return their declared content type | `probe_tool_surface` (27/27) — includes the error paths | PASS |

### F. UI and rendering — *the agent can look at the model*

| # | the promise | test | status |
|---|---|---|---|
| A20 | `export_view` returns an image, not text | `probe_tool_surface`, `verify_export_view` | PASS |
| A21 | A UI toggle changes state and restores it | `probe_ui_and_rendering` (10/10) | PASS |

### G. Security — *what we say is refused is refused*

| # | the promise | test | status |
|---|---|---|---|
| A22 | Every always-blocked pattern is refused at **both** layers | `probe_security_scan` (24 patterns × 2 layers) | PASS |
| A23 | Agent-only patterns are refused on the agent path and allowed on the console path | `probe_security_scan` (3 documented allowances) | PASS |
| A24 | Qualifying a type name is not a way around a refusal | `probe_scan_bypass` (16/17) + `probe_scan_bypass_exe` (7/8) | **FIXED, awaiting install** — the one failure in each is the installed add-in's prose scan, which the new build fixes. See §5 F1 |

### H. Hygiene — *the test rig does not damage the thing it tests*

| # | the promise | test | status |
|---|---|---|---|
| A25 | No probe leaves the model changed | post-run sweep: 609 walls · 27 wall types · 0 comments · 0 probe types · 0 duplicate names | PASS |
| A26 | Every gate is green, or red for a reason that is out of scope and named | `python .repl/gate.py` | PASS (17 auto green · `mcp-exes` = the 4 out-of-scope siblings · 1 known-red F5) |

### 3.1 Which build each verdict belongs to

⚠ **A verdict is bound to a build.** Change either artifact and every row reverts to
UNMEASURED until it is re-run. That is not bureaucracy — the `Duplicate` regression (ROUND 33)
appeared in a build whose predecessor had passed the same probe.

| build | engine DLL | `paracore-gen.exe` | what it is |
|---|---|---|---|
| **A** — the last fully measured build | `b63ee4d5…` 374,272 B | `40035179…` 26,674,229 B | every row in §3 above was measured on this build |
| **B** — the current build | `e0763ff5…` 374,784 B | `779870c7…` 26,675,996 B | carries the F1–F4 fixes; **not installed**, so only the rows provable without an install have been re-run |

**What has been re-run on build B without installing anything** (the scan runs before any gRPC
call, so these need no Revit):

| check | result |
|---|---|
| qualified `Thread` / `HttpClient` / `Socket` / `Process` / `StreamWriter` refused by the frozen exe | 5/5 |
| a read-only query still executes through the frozen exe (no blanket refusal) | PASS |
| the frozen exe's read-only guard refuses a qualified `Transaction` | PASS |
| a comment naming a write does not refuse a correct query | **FAIL — the INSTALLED add-in still refuses it**; build B fixes that layer and it will pass after install |
| engine DLL carries `TransactionGroup(` and no longer carries the old `new Transaction` verb | verified by byte search |

**Every other row must be re-run after the install.** They were green on build A; build B
changes `MightWrite`, `StripCodeNoise` and the read-only backstop, all of which sit on the
paths those rows exercise, so build A's green is not evidence about build B.

## 4. The severity bar

Rank a finding by **what the user loses**, never by how hard it was to find.

| severity | definition | blocks release? |
|---|---|---|
| **Sev-1** | A silent wrong answer, a partial write reported as clean, data loss, or a security promise that does not hold. The user acts on a false statement. | **YES** |
| **Sev-2** | A capability in §3 does not do what the row promises. | **YES** — fix it or cut the capability |
| **Sev-3** | Friction, a misleading message, or a rule that fires on prose. No wrong outcome. | no — §5 |

Two tests that decide most arguments:

- **Would the user know?** If the product tells the truth about a limitation, it is Sev-3. If it
  says "done" and is wrong, it is Sev-1.
- **Is the code unreachable, or wrong?** A guard that is correct but never runs is Sev-2, because
  the promise attached to it is false. (ROUND 33: the rollback sentence was right and
  `WriteVerbs` never let it run.)

## 5. Open findings — disposition

Everything here is measured, and everything here is outside §3 unless stated.

| id | finding | sev | disposition |
|---|---|---|---|
| **F1** | A **qualified** type name walked past every constructor pattern: `new System.Threading.Thread(…)` executed; `new Autodesk.Revit.DB.Transaction(…)` was not refused by the read-only guard; `new System.IO.StreamWriter(…)` walked past the **file policy** — the most expensive list of the three. | **Sev-1** (A24) | **FIXED** — the namespace prefix is blanked once before scanning, in all three Python scans and in the add-in; `global::` prefixes are covered too |
| **F2** | `MightWrite` scanned raw source, so a write verb inside a **comment or string** opened an empty `TransactionGroup`. My own code comment claiming "a query never opens a group" was therefore false. | Sev-3 | **FIXED** — `StripCodeNoise` in the engine; the comment now states the one case it cannot rule out |
| **F3** | `MightWrite` missed a qualified `new …Transaction(` (its verbs were `"new Transaction"` / `"TransactionGroup"`), so such a script got **no envelope** and a failed raw write got no rollback sentence. | **Sev-2** (A10/A11) | **FIXED** — verbs are now `"Transaction("` / `"TransactionGroup("`, which also covers `SubTransaction(` |
| **F4** | The read-only guards scanned prose, in **both** layers: a comment mentioning `new Transaction` refused a correct query. Fixing only Python left the add-in refusing it one layer down — measured from the frozen exe. | Sev-3 | **FIXED** — `strip_code_noise` in the Python guard, `StripCodeNoise` in the add-in backstop |
| **F5** | `workspace-map` gate is known-red (F5, pre-existing). | — | **NOT THIS RELEASE** — recorded, unchanged |
| **F6** | Whether committing an **empty** `TransactionGroup` sets `IsModified` is **unmeasured**. The probe that would settle it needs a clean document and the demo file is dirty. | — | **MEASURE after the next save** — do not claim either answer until then |
| **F7** | A **target-typed** construction (`StreamWriter w = new(path);`) names no type, so no `new <Type>(` rule can see it. | Sev-3, named limitation | **NOT FIXED, on purpose** — refusing `new(` outright would refuse `Params p = new();`, which is a documented gallery pattern. The read-only path is still protected by the always-rollback group; the file policy remains a best-effort net, as its own message says |
| **F8** | The first version of `probe_scan_bypass` reported four "holes" that were not holes: it expected `execute_dynamic_query` to refuse `new Transaction(`, which is a **legal** way for a script to group its own writes. Its control case failed and that is what exposed it. | probe defect | **FIXED** — the probe now tests each type on the layer that owns it, with a control on each side |

⚠ F1 and F3 are the same defect wearing two hats: **a rule written against a short name, and a
caller free to write the long one.** F2 and F4 are the mirror pair: **a scan that reads prose.**
Fixing the pair rather than the instance is why the change is one normalization step per scan
plus one noise-strip call, instead of eleven new patterns.

⚠⚠ **Which layer owns which type** — this is where the first probe went wrong, and getting it
wrong makes a working guard look broken:

* `explore_revit_data` (read-only) **must** refuse `Transaction` / `TransactionGroup` /
  `SubTransaction`. Discovery is the whole point of that tool.
* `execute_dynamic_query` (write) **must not**. A raw `new Transaction(Doc)` is a legal way for a
  script to group its own writes — `Transact()` is a wrapper around exactly that.
* `Thread` belongs to the agent path only; a background thread is not a model change.

A probe whose **control** fails has a wrong expectation, not a product with a bug. Every case
above now has a control on the other side of the line.

## 6. How to run it

```bash
# the gates — one command, one verdict
python .repl/gate.py                 # --list says what each protects; exit 2 = could not look

# the scan criterion, BEFORE anything is installed — needs no Revit for the refusals,
# because the scan runs before any gRPC call. Point it at the built exe.
cd paracore-gen/spikes
<venv>/python.exe probe_scan_bypass_exe.py ../dist/paracore-gen.exe

# the live suite (Revit open, document loaded, add-in + MCP installed)
<venv>/python.exe probe_rewriter_live.py
<venv>/python.exe probe_engine_regressions.py
<venv>/python.exe probe_write_safety.py
<venv>/python.exe probe_bulk_warning.py
<venv>/python.exe probe_catalog_search.py
<venv>/python.exe probe_type_write_advisory.py
<venv>/python.exe probe_ui_and_rendering.py
<venv>/python.exe probe_tool_surface.py
<venv>/python.exe probe_security_scan.py
<venv>/python.exe probe_scan_bypass.py
<venv>/python.exe verify_rollback_live.py
```

⚠ The interpreter matters: the probes need `mcp`, `grpc` and `protobuf`, which only the build
venv (`paracore-gen/mcp-build/.venv/Scripts/python.exe`) has. A system Python fails at import
and looks like a product failure.

⚠ `probe_scan_bypass.py` and `probe_scan_bypass_exe.py` answer different questions. The `_exe`
one proves the **frozen artifact** carries the fix; the other proves the **source** does, against
the running engine. Both are needed, because a PyInstaller bundle is a copy.
