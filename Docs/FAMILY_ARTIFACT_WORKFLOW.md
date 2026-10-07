# Family build artifacts — the script is the source of truth

**Status:** convention, in force
**Date:** 2026-10-02
**Scope:** every loadable family (`.rfa`) authored through this MCP
**Related:** [`FAMILY_EDITOR_PLAN.md`](FAMILY_EDITOR_PLAN.md) §6.3 (procedure library),
[`REVIT_MCP_LANDSCAPE.md`](REVIT_MCP_LANDSCAPE.md) §4.5 (`promote_script`)

---

## 1. The loop we actually run

The user's own description, verbatim:

> *"so i opened the family in Revit, then see some defects, then i come heare and tell you what
> is wrong. then you inspect the opened .rfa file to relate with what i am saying, then you
> create it again. then i close it and open it again. then the adjustment is seen in the newly
> opened family."*

That loop works. Nothing here replaces it. The question is what the **agent** is holding when
step four — *"you create it again"* — begins.

Today it holds nothing. It reads the live `.rfa` through the MCP, infers what the family was
meant to be, and **re-writes the entire build from scratch**. Every revision is a fresh
composition, and the previous revision is gone.

This document makes the build script a **durable, named artifact**, so a revision is an
**edit to a file** rather than a re-invention.

---

## 2. What is actually lost — measured 2026-10-02

Before designing anything, check whether the past work is recoverable.

**The families survive.** All six are in `C:\Users\seyou\Documents\`:

| file | built | bytes |
|:---|:---|---:|
| `MetricChair.rfa` | 2026-09-30 21:07 | 471,040 |
| `ParametricChair.rfa` | 2026-09-30 21:23 | 479,232 |
| `ParametricChair_v2.rfa` | 2026-10-01 16:46 | 483,328 |
| `ReferencePlaneChair.rfa` | 2026-10-01 19:21 | 479,232 |
| `Sofa_3-Seater_Metric.rfa` | 2026-10-01 20:24 | 503,808 |
| `Paracore_Single_Door.rfa` | 2026-10-01 21:00 | 516,096 |

**The scripts do not.** `mcp_core/tools.py:295` is the only trace:

```python
logger.info(f"Executing dynamic query: {justification}")
```

The **justification** — a one-sentence natural-language summary — is logged. The **C# is not
written to disk anywhere.** It is passed to `execute_repl()` and executed.

Confirmed by search:

- `CompiledScript.cs` (58 KB) is the **takeoff export** script, last written 2026-09-24 — three
  days *before* the chair work. Not it.
- No `.cs` outside `logs/` anywhere under `%APPDATA%\paracore-data`.
- `%TEMP%`, `Documents`, `Desktop`, `Downloads`: no family build scripts.
- The MCP log holds ~15 chair queries and ~8 sofa queries as **intent sentences only** —
  enough to reconstruct the *history of what was attempted*, not the code.

So the chair and sofa revisions are **not recoverable**. The door's swing-line fix — which was
made by editing the live document, not by a script — is likewise gone as a reproducible step.

**What did survive is the knowledge.** Every hard-won fact from those sessions was distilled
into `mcp_core/skills/family-authoring/SKILL.md` (35 KB, last touched 2026-10-01 21:00, minutes
after the door). The `Extrusion Start` stacking chain, the `ComputeReferences` trap, the
modal-dialog hazard on `Exterior`/`Interior`, the hinge-apex rule — all of it is there.

That is the shape of the loss precisely: **the lessons were kept, the code was not.** This
document is about keeping the code too.

---

## 3. Why the script beats reading the `.rfa`

The obvious objection: *the family is on disk and the MCP can read it, so why keep the script?*

Because they answer different questions.

| | `.rfa` (read through the MCP) | `build.cs` |
|:---|:---|:---|
| records | what the family **IS** | what the family was **MEANT to be** |
| parameters | current values | the parameter list *and* the formulas *and* why |
| forms | 11 extrusions, ids, extents | the same 11, in source order, with names |
| bindings | each form's `Start`/`End` association | the association **and** the intent behind it |
| a defect | visible as a value that looks wrong | visible as a **diff** |

That last row is the whole argument. When the user says *"the armrests overlap the frame"*, the
`.rfa` shows two extrusions whose `Extrusion Start` is bound to `Leg Height`. It cannot say
whether that binding was **deliberate** — a form that legitimately starts low — or the
**defect**. The script can, because in the script the defect is one line that reads differently
from its neighbours.

**A defect is a diff. The `.rfa` has no diff.**

Three consequences follow, and they are the practical value:

1. **Diagnosis is cheaper.** The agent compares the user's report against *intent*, not against
   a wall of bindings it must first reverse-engineer.
2. **The fix is auditable.** Today a revision produces a new binary and no record of what
   changed. With a script, the change is a readable diff.
3. **The fix is reversible.** A wrong fix is one line reverted, not the family re-described.

⚠ **And the `.rfa` cannot be diffed at all** — it is a binary blob. That is why §6 adds a
**manifest**: a generated, textual projection of the `.rfa` that *can* be diffed.

---

## 4. Layout

```
C:\Users\seyou\Documents\ParacoreFamilies\
    README.md                        the convention, one page
    ParametricChair\
        build.cs                     the ONLY build script — rebuilds from the template
        manifest.json                generated: the state of the shipped .rfa
        CHANGELOG.md                 one entry per revision; quotes the user's report
    Sofa_3-Seater_Metric\
        build.cs
        manifest.json
        CHANGELOG.md
```

**Why `Documents\ParacoreFamilies\`, and not a repo.**

- The families are **user work products**, not tool source — **and the tool ships.**
  ⚠⚠ **VERIFIED 2026-10-02:** the whole `paracore-mcp` working tree is copied into
  `paracore/rap-web/src-tauri/server-release/paracore-mcp/`, and `tauri.conf.json:82-83`
  declares `server-release` as a **bundle resource** — so it goes into the shipped installer.
  Confirmed by listing the built installer (see §13). A specific villa's furniture does not
  belong in a distributed product.
- It sits beside the `.rfa`s the user already saves to `Documents`, so the artifact is where
  the deliverable is.
- Keyed **by family name**, so it is robust to the user moving the `.rfa`: the manifest records
  the absolute `.rfa` path.

**The tooling ships; the work stays local.** The convention, the template and the manifest
spec live in `paracore-mcp/` (§9) — they *should* ship, because every user benefits. The user's
families live here.

⚠ **This is not a hypothetical.** Placing these families under `paracore-mcp/` would have put
them in the installer alongside everything else that is already there — see §13.

---

## 5. The authority rule

> ### The script is the source of truth. The `.rfa` is a build output.

This is the same hazard class as `MASTER_SYSTEM_SPEC.md` §3: a generated file that can be edited
directly, and is silently clobbered when its generator re-runs.

**Editing the open `.rfa` directly is allowed.** Sometimes it is the only practical move — the
door's swing lines were mirrored in place, reusing the template's own `SketchPlane`, because
re-creating the template's symbolic curves from scratch would have been worse.

**But a direct edit is not durable until it is folded back into `build.cs`.** Otherwise the next
rebuild silently reverts it — and the user, who reopened the file and saw the fix, will see it
disappear for no visible reason.

### The divergence gate

The rule needs teeth, or it is a convention nobody checks.

> **Rebuild from `build.cs` → regenerate `manifest.json` → diff against the shipped manifest.
> Zero diff = the script and the file agree. Any diff = the script is stale.**

This is cheap, mechanical, and it is the *only* honest answer to "is the script current?" It is
the same discipline the rest of this workspace runs on: assert the thing you claim, and make the
assertion able to fail.

⚠ It must be run **after** a rebuild, never against the file alone — a manifest regenerated from
an unchanged `.rfa` will of course match itself. The comparison is only meaningful when the
`.rfa` was produced *by the script*.

---

## 6. The manifest

`.rfa` is binary. `manifest.json` is its diffable projection, generated by reading the family
back through the MCP.

```jsonc
{
  "family": "ParametricChair",
  "rfa": "C:\\Users\\seyou\\Documents\\ParametricChair.rfa",
  "rfa_bytes": 479232,
  "generated": "2026-10-02T15:41:07",
  "template": "English\\Metric Generic Model.rft",
  "types": ["Standard 450", "Large 900"],

  "parameters": [
    { "name": "Chair Width", "spec": "length", "instance": false,
      "formula": null, "values": { "Standard 450": 450.0, "Large 900": 900.0 } },
    { "name": "Seat Top", "spec": "length", "instance": false,
      "formula": "Seat Height + Seat Thickness", "values": { } }
  ],

  "forms": [
    { "id": 2802, "kind": "Extrusion",
      "start_binding": "(LITERAL)", "end_binding": "Leg Height",
      "extents": { "x": [0, 40], "y": [0, 40], "z": [0, 405] } }
  ],

  "overlapping_pairs": 0,
  "warnings": []
}
```

### Why the bindings are the point

⚠⚠ **`start_binding` / `end_binding` record the ASSOCIATION, not the value** — because the
value is not evidence. Per the skill: `AsValueString()` on an associated parameter returns the
**resolved** value, so a hardcoded `300` and a bound `300` are indistinguishable by reading.

Only `FamilyManager.GetAssociatedFamilyParameter(p)` tells you which you have. So the manifest
carries the binding name, and a literal is recorded as `(LITERAL)`.

That is exactly the field that would have caught the sofa defect: **both armrests' `Extrusion
Start` were associated to `Leg Height` (150) instead of `Frame Top Height` (300)** — 2 of 11
forms, and the only two that were wrong. A manifest diff across the fix shows those two lines
and nothing else.

Also carried, per `FAMILY_EDITOR_PLAN.md` §4 Tier 1:

- `overlapping_pairs` — the bounding-box intersection count, computed with a strict `<` and a
  tolerance so forms that merely **touch** at a shared Z do not count.
- `warnings` — `famDoc.GetWarnings()`, so a family that saved with complaints says so.

### Generation

The manifest is produced by a read-only script run through `explore_revit_data`, after the
build commits. The generator is part of the convention, not of the MCP — see §9.

---

## 7. The changelog

`CHANGELOG.md` is the third artifact, and it is the one that most improves **context** — which
is what the user actually asked for.

```markdown
## r3 — 2026-10-01

**Reported:** "the armrests are sinking into the frame, they start too low"

**Diagnosed:** both armrests' `Extrusion Start` bound to `Leg Height` (150).
Correct chain is legs → frame → seat/arms/back, so an arm starts at
`Frame Top Height` (300). 2 of 11 forms affected — the only two.

**Changed:** 2 lines in `build.cs` (armrest start bindings).

**Manifest diff:** `forms[7].start_binding` and `forms[8].start_binding`,
`Leg Height` → `Frame Top Height`. No other field moved.
```

Two reasons this earns its place:

1. **It quotes the user's words verbatim.** The next session needs to know what has *already*
   been reported and what was *rejected*. Without it, the agent re-proposes a fix the user
   already turned down — the most annoying possible failure of context.
2. **It records the manifest diff.** The claim "I changed only the armrests" becomes checkable
   rather than asserted.

⚠ Revit already keeps `.0001` / `.0002` backups beside a saved family — `Sofa_3-Seater_Metric`
has both. They are **binary and unlabelled**. The changelog is what those backups are not:
readable, dated, and annotated with the reason.

---

## 8. The loop, with the artifacts in it

| # | step | artifact touched |
|:---|:---|:---|
| 1 | agent reads `build.cs` + `manifest.json` + `CHANGELOG.md` **before** touching anything | all three |
| 2 | agent reads the live `.rfa` through the MCP — the *current* state, which may differ if the user edited it in Revit | — |
| 3 | user reports a defect, in his own words | — |
| 4 | agent **edits `build.cs`** — a diff, not a rewrite | `build.cs` |
| 5 | agent runs it → new `.rfa` | — |
| 6 | agent regenerates `manifest.json` and **diffs it against the old one** — the diff is the proof of what changed | `manifest.json` |
| 7 | agent appends a changelog entry quoting the report + the diff | `CHANGELOG.md` |
| 8 | user closes and reopens the family — sees the change | — |

Steps 1, 4, 6 and 7 are new. Step 6 is the one that matters: **the manifest diff replaces "trust
me, I fixed it"** with something the user can look at.

Steps 2 and 8 are unchanged. The user's loop is not being redesigned — it is being given a
memory.

---

## 9. Relationship to the procedure library

`FAMILY_EDITOR_PLAN.md` §6.3 already proposes a general **procedure library**
(`search_procedures` / `run_procedure` / `promote_procedure`), citing Horizun's `promote_script` —
*"so it stops being ad-hoc code."* `REVIT_MCP_LANDSCAPE.md` §4.5 lists it as **the gap we most
lack**.

This document is the **narrow, immediately-usable slice of that idea**:

| | §6.3 procedure library | this document |
|:---|:---|:---|
| scope | any verified script | family build scripts |
| storage | MCP-side, searchable | on disk, keyed by family |
| discovery | `search_procedures` | a conventional path, named by the skill |
| MCP change | new tools | **none** |
| ships? | yes, to every user | no — local work product |

So it can be adopted **today, with no MCP change and no rebuild**, and it establishes the shape
the general library would generalise. If §6.3 is built later, these directories are its first
entries.

⚠ **The one thing this needs from the MCP is a rebuild** — the pointer in the skill (§10) is
bundled by `paracore-mcp.spec`, so it does not reach the *running* MCP until the server is
rebuilt and reinstalled. Until then the convention is live in the repo and in the local folder,
but the served `skill://family-authoring/SKILL.md` will not mention it.

---

## 10. Where this is referenced

- `mcp_core/skills/family-authoring/SKILL.md` — "Durable build scripts" section, pointing here
  and at the template. **Bundled** → needs a rebuild to ship.
- `mcp_core/skills/family-authoring/build-template.cs` — the skeleton. **Bundled** (the spec
  copies the whole `mcp_core/skills` directory).
- `C:\Users\seyou\Documents\ParacoreFamilies\README.md` — the one-page version, where the
  families are.

---

## 11. Writing a `build.cs` that survives the compliance layer

Two things bite when you write a *documented* script — a script whose comments explain the API,
which is exactly what `build.cs` should be.

⚠⚠ **The compliance layer scans COMMENTS, not just code.** So a comment that spells a forbidden
token is rejected like code. Found by running `build-template.cs` through the checker, not by
reading the rules:

| written in a comment | result |
|:---|:---|
| `…THROW on a project document.` | ❌ **blocked** — matched the `document.` hard error |
| `…always reads the ACTIVE document. In family work…` | ❌ **blocked** — same rule |
| `Autodesk.Revit.Creation.ItemFactoryBase` | ⚠ lint note — the namespace prefix |

The first two were a **false positive on the blocking layer** (D-MCP-6): the rule meant to catch
the identifier `document.SaveAs` also matched the English word at the end of a sentence. Fixed
with a `(?=\w)` guard — a real member access still blocks, prose does not.

**Practical rules for `build.cs`:**

- Never end a comment with `document.` or `doc.` — rephrase to *"…the active document is a
  PROJECT —"*. ⚠ On a **deployed** MCP older than the D-MCP-6 fix, this is a hard block.
- Write the namespace as `Creation.ItemFactoryBase`, not with the `Autodesk.Revit.` prefix.
- Two lints will fire on **correct** family code, and both were narrowed on 2026-10-02
  (D-MCP-7) so they no longer do:

  | lint | why family work must use it anyway |
  |:---|:---|
  | `new FilteredElementCollector(...)` | `GetElements<T>()` has **no document overload** — it always reads the ACTIVE document. Family work is on a *second* document. |
  | `get_Parameter(BuiltInParameter.X)` | returns the **`Parameter` object**, which `GetStr`/`GetNum` cannot supply — needed for `GetAssociatedFamilyParameter` and `AssociateElementParameterToFamilyParameter`. |

  Until the MCP is rebuilt, the lints still fire — they are **advisory**, the code still runs, and
  the template says so in a comment.

**Verify, do not assume.** `spikes/verify_lint_narrowing.py` asserts every exemption by
**identity and in both directions** — the exempt form must not fire, the flagged form must still
fire, and `build-template.cs` must itself pass `check_paracore_compliance`. A count of lints
cannot distinguish "the rule was narrowed" from "the rule was deleted".

---

### And two API facts the template encodes

Both were checked against the Revit API reference while writing it, and **both would have made a
naive template wrong** — which is the argument for reading the reference rather than recalling the
API:

- ⚠⚠ **`SaveAs` returns `void`.** There is no bool to test; `if (doc.SaveAs(p) == false)` does not
  compile. Use `File.Exists(path)` as a post-condition instead.
- ⚠⚠ **`SaveAs(String)` raises `InvalidOperationException` — *"There is an existing file at
  filepath"* — when the target already exists.** That is **exactly the rebuild case**, and
  rebuilding is the normal way a family is revised. So `SaveAsOptions.OverwriteExistingFile = true`
  is **required, not optional**.

Both are now recorded in `skill://family-authoring/SKILL.md` §"Saving and loading".

---

## 12. What this deliberately does not do

- **No new MCP tools.** The convention is files, a template and a rule. Tools can come later if
  the convention proves itself.
- **No automatic capture.** The MCP could persist every `execute_dynamic_query` body, but that
  is a transcript, not a procedure — ~15 exploratory probes per family, of which one or two are
  "the build". Capturing all of it buries the artifact. **The script is curated, not logged.**
- **No change to the user's loop.** He still opens the family, reports the defect, closes and
  reopens. The artifacts are for the agent's side of the conversation.
- **No computer use.** Consistent with `REVIT_MCP_LANDSCAPE.md` §7 — the API is faster, exact,
  and in-process. Screen-driving gives up the in-process advantage for nothing.

---

## 13. ⚠⚠ A verified leak — why "the tooling ships" is not a figure of speech

Found while choosing a home for the build scripts. It is **not** a family-authoring problem, but
§4's decision rests on it, so it is recorded here. **Owner: `paracore` (rap-web packaging).**

### The mechanism

`paracore/build-frontend.ps1:142` bundles the MCP into the desktop app:

```powershell
robocopy $agentSource (Join-Path $serverReleaseDir "paracore-mcp") /E `
    /XD .venv __pycache__ .ruff_cache .git mcp-build build dist installers /XF *.spec *.pyc
```

`/E` copies the **whole tree**. The `/XD` list is therefore the *only* thing between the working
directory and the shipped installer — and it did not list `.workbuddy-ai`, `spikes`, `graphify-out`,
`tests`, or `.claude`, and `/XF` did not exclude `*.log` or the dotfile scratch.

`paracore/rap-web/src-tauri/tauri.conf.json:82-83` declares `server-release` as a **bundle
resource**, so whatever lands there goes into the installer.

### The evidence — measured, not inferred

`7z l Paracore_4.7.0_x64-setup.exe` (built 2026-10-02 07:30, from a `server-release/` staged at
07:26) contains:

| entry | size |
|:---|---:|
| `server-release\paracore-mcp\.workbuddy-ai\memory\2026-09-30.md` | 87,850 |
| `server-release\paracore-mcp\.workbuddy-ai\memory\2026-10-01.md` | 33,059 |
| `server-release\paracore-mcp\.workbuddy-ai\memory\2026-10-02.md` | 4,495 |
| `server-release\paracore-mcp\.workbuddy-ai\memory\MEMORY.md` | 5,096 |
| `server-release\paracore-mcp\paracore_mcp.log` | 1,372 |
| `server-release\paracore-mcp\spikes\DoorScratch.rfa` | 495,616 |

plus **20 files** under `spikes\`. The `.workbuddy-ai` memory is the agent's own project notes —
client project names, defect lists, business context.

⚠ The MSI is built from the same staging; its file table is not greppable the same way, so the
NSIS installer is the one proven by listing. Treat both as affected.

### The fix — applied 2026-10-02

`/XD` gained `.workbuddy-ai .claude .pytest_cache graphify-out spikes tests`; `/XF` gained
`*.log .mcp_proc.txt .revit_state.txt .repl_proc.txt`.

⚠ **Existing installers still contain the leak** — they would need a rebuild to be clean.

⚠ **And this is why the families are not in a repo.** Had they gone under `paracore-mcp/`, they
would have been in that installer too. `spikes/DoorScratch.rfa` shows it is not a hypothetical:
it is **untracked** in git, and it shipped anyway — because `/E` does not consult `.gitignore`.
