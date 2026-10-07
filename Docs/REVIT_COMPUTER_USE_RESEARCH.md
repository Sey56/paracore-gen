# Revit + computer use — possible, demonstrated, and still the wrong tool

**Date:** 2026-10-02
**Prompted by:** a fair challenge to a claim in `REVIT_MCP_LANDSCAPE.md` §5 and §7.
**Purpose:** establish what is actually possible, correct an error in the earlier reasoning, and say
where computer use genuinely earns its place.
**Method:** public sources read directly, plus the empirical computer-use benchmarks. Figures are as
published; the space moves weekly.

---

## 1. The claim under examination

From `REVIT_MCP_LANDSCAPE.md` §5:

> **No Revit MCP in the field models by driving the GUI.** Every capable server — including
> Autodesk's own — uses the API. hungpixi's threading section explains why: direct socket-thread
> writes cause *"immediate memory crashes"*, and everything must be marshalled through
> `ExternalEvent` into Revit's own idle loop.
>
> That is external confirmation of the earlier recommendation: **computer use belongs as a camera,
> not a hand.**

And §7, "What to deliberately not do":

> **Do not build GUI-driving modelling. Nobody in the field does it, and the threading model
> explains why.**

**The conclusion was right. The reasoning was wrong, and the phrasing overstated it.** Two distinct
errors, and they need separating because only one of them is a matter of emphasis.

---

## 2. Error 1 — ⚠⚠ the threading argument is a non-sequitur

This is the substantive mistake, and it is a clean conflation of two different things.

`ExternalEvent` marshalling exists because the **Revit API** is not thread-safe: a method that
touches the document must run on Revit's own UI thread. Call it from a socket thread and you get
the crashes hungpixi documents. That is a constraint on **calling the API from the wrong thread**.

**GUI automation never calls the API.** It injects OS-level input events — `SendInput`, or the UI
Automation (UIA) pattern — which Windows dispatches to the foreground window's message queue.
Revit's UI thread pumps that queue. The input *arrives as ordinary user input*, on the UI thread,
by construction. There is no cross-thread API call, so there is nothing for `ExternalEvent` to fix
and nothing for the threading model to forbid.

> **The threading constraint does not argue against GUI automation at all.** I used it as if it did.
> It argues against *off-thread API calls* — a completely different failure mode, in a completely
> different mechanism.

A real hazard does exist in this area, and it is worth naming so the correction is not read as
"GUI automation is safe": **UIA is a cross-process protocol and a call can block while the target
application is busy.** So a GUI agent driving a Revit that is mid-computation can hang — which is
the same "busy Revit is indistinguishable from dead Revit" problem the landscape doc already
records in §3.1. That is a genuine argument, but it is an argument about *robustness*, not about
*possibility*, and it is not the argument I made.

---

## 3. Error 2 — "nobody does it" was written as if it settled "can't"

"No Revit MCP in the field models by driving the GUI" is, as far as this research can find, still
**true as a description of the field**. But it is an observation about where people have chosen to
invest, and I let it do the work of a feasibility claim.

Those are different statements:

| Statement | Status |
|---|---|
| No production Revit MCP drives the GUI | **True** — verified across the field survey |
| GUI-driving Revit is impossible | **False** — it works, and it is demonstrated |
| GUI-driving Revit is the wrong tool for production modelling | **True** — for reliability reasons, §5 |

The honest version of my sentence is the third one, and it needs the evidence in §5 to stand up.

---

## 4. What is actually possible

**Yes, a computer-use agent can drive Revit's GUI.** The mechanism is well established:

1. **Screen capture** — a screenshot of the Revit window.
2. **Inference** — a vision model decides the next action ("click the Wall button", "type 3000").
3. **Input injection** — `SendInput` / UIA moves the mouse, clicks, types.
4. Repeat.

Windows UIA can additionally see the **ribbon, dialogs, palettes and the Properties grid** as
structured controls, so an agent does not have to work purely from pixels for those. It can find a
button by name rather than guessing coordinates.

So the user's reading is correct: **clicking buttons, opening dialogs, setting values and closing
them is mechanically possible**, and it is exactly what the general computer-use products do.

**One important asymmetry, though.** Revit's 3D view is a custom-rendered surface, not a tree of
UI controls. UIA exposes *the window*; it does not expose *the walls inside it*. So in the model
view the agent is working from pixels — it cannot ask "what is the volume of that wall", it can
only look at it. (This is analysis, not a measured claim.)

That asymmetry matters more here than anywhere else, for the reason in §5.2.

---

## 5. Why it is still the wrong tool for production modelling

Four reasons, in order of how much they cost.

### 5.1 Error compounds — and modelling is a long horizon

The 2026 computer-use benchmark picture (OSWorld, 369 real desktop tasks, human expert baseline
**~72.4%**):

| Agent | OSWorld score | Note |
|---|---|---|
| OSAgent | **76.26%** | independent evaluation |
| GPT-5.4 | 75.0% | self-reported; first above-human claim |
| Claude Opus 4.6 | 72.7% | independently assessed |
| Claude Sonnet 4.6 | 72.5% | independently assessed |
| Human expert | ~72.4% | reference |

⚠ A vendor blog claims 82% for its own product. **Unverified self-reported marketing — treat as
indicative at best.**

The headline is not the score. It is this, from the benchmark analysis:

> **"Success rates drop sharply once a workflow requires more than five or six sequential
> decisions, compounding errors at each step."**

Model a building and you are not at five or six decisions. You are at hundreds. Even at a
generous 95% per action, 100 actions gives **0.6%** end-to-end. The videos show short tasks
because short tasks are what survives.

Supporting numbers, same source:

- Agents take **1.4–2.7× more steps** than a human for the same task.
- End-to-end latency **in tens of minutes** for workflows a human completes in under three.
- A **~37% gap** between benchmark scores and production deployment, attributed to **UI drift**,
  long-tail failure modes, and evaluation fidelity.
- Three persistent failure modes: **GUI grounding** (misjudged click coordinates, *especially when
  UI elements shift between runs*), **operational knowledge**, and **long-horizon planning**.

⚠ **UI drift is the one that kills a product.** A benchmark freezes its application. Revit does
not: 2023 → 2027 differ, ribbon layouts change with which add-ins are installed, and DPI, window
size and UI language all move the pixels. An agent tuned on one machine is not an agent.

### 5.2 Precision is the product

This is the decisive point for Paracore specifically.

A vision model clicks *approximately* there. Revit snaps — but the agent cannot reason about
**which** snap it hit, and cannot verify the result by looking. For a drawing tool that is
tolerable; a wall 50 mm out is still a wall. **For a takeoff it is fatal, because the deliverable
is the number.**

Paracore's entire value is measured quantity, and its whole defect register is the same mistake
wearing different hats: *a nominal figure standing in for a real one*. GUI automation reintroduces
that class of error by construction — the agent causes geometry it cannot measure, then you still
need the API to read it back. You would pay the reliability cost of the GUI **and** the
integration cost of the API, to get a worse answer than the API alone.

### 5.3 No transaction, no rollback, no verification

The API gives a `Transaction`: wrap, act, re-read, roll back on failure. That is the mechanism
behind the verified-write contract the landscape doc recommends adopting (§4.1). GUI clicking has
no such handle. There is no atomic unit to undo, and no way to prove the write landed other than
looking at the screen.

### 5.4 Modal state and blast radius

Revit is full of modal dialogs, sketch modes and "cannot be ignored" warnings. A misfire can leave
the document in a state the agent cannot diagnose or exit. Against a real project — a real
building — that is not an acceptable failure mode.

---

## 6. What the videos are actually showing

Worth being precise, because this is where the impression comes from. Three categories.

**(a) API-based, described in the language of canvas control.** This is the majority.

The clearest evidence found is `vahidrahimiarchitect/Revit-AI-BIM-Agent-claude`, which markets
itself as:

> *"Autonomous Revit Control: Functions as an intelligent agent that **directly interfaces with the
> Revit canvas** to generate and modify parametric building elements…"*

and then states its own architecture:

> *"Execution Layer: Executes native commands within the Autodesk Revit environment using Python
> and C# **via the Revit API**, dynamically modifying the project database."*

**"Directly interfaces with the canvas" is a description of the user experience, not of the
mechanism.** This is what most "Claude + Revit" and "ChatGPT + Revit" demos are: an MCP server or a
plugin, called by the agent, executing deterministic API calls. It looks like the AI is modelling.
It is — through the API. Which is exactly what Paracore does.

**(b) Genuine computer use on short tasks.** Also real. Create a wall, place a door, change a
parameter, take a screenshot, orbit the view. This works, and the demos are honest about what they
show — they are simply short, per §5.1.

**(c) Hybrid.** Computer use for navigation and visual inspection, API for the actual modelling.
This is the shape the evidence actually supports, and it is what §7 recommends.

⚠ **Demos are curated.** Nobody posts the 40-step run that stalled on a dialog.

---

## 7. Where computer use genuinely belongs

My conclusion — *camera, not a hand* — survives. It should be re-based on cost/benefit, not on
threading:

| Use | Why the GUI is right |
|---|---|
| **Verification / visual QA** | "Does this dialog say what I think?" Reading the screen is cheap and needs no API. |
| **UI-only corners** | Family Editor sketch mode; dialogs with no API surface; third-party add-ins. |
| **API gaps** | Real and documented. `REVIT_MCP_LANDSCAPE.md` §3.7 records `ScheduleFieldType.Formula` having no public formula-string setter in this API version. A GUI fallback is the only route to that control. |
| **Navigation / inspection** | Orbiting, section boxes, screenshots for a report — actions whose *output is a picture*. |

The rule that follows: **use the GUI where the output is a picture or a UI state; use the API
where the output is a number or geometry.** A click that *creates* geometry is a number in
disguise, and it should go through the API.

Note that `FAMILY_EDITOR_PLAN.md` already gets this right — Tier 2 prefers API image export over
screen capture precisely because it is *"deterministic, resolution-controlled, and does not require
Revit to be the foreground window"*, and reserves real screen capture for *"dialogs that API image
export cannot see."* That reasoning is correct and needs no change.

---

## 8. What this changes

1. **`REVIT_MCP_LANDSCAPE.md` §5 and §7** — the threading justification and the "nobody does it"
   phrasing are corrected in place. The recommendation is unchanged.
2. **No change to the plan.** Paracore's architecture — API + fluent DSL, computer use as a camera —
   is the right one, and this research strengthens the case by giving it the correct reason.
3. **One thing worth adding to the gap list** (§6 of the landscape doc): if a GUI fallback is ever
   built for the API-gap corners, it should be **UIA-based, not vision-based**, so it can address
   controls by name instead of by coordinate. That removes the GUI-grounding failure mode for
   exactly the dialogs it would be used on.

---

## 9. Does anyone need to *watch*? Process visibility is not a requirement

**The question.** If the deliverable is the artifact — a `.rfa`, a BOQ, a model — what is the value
of *seeing* the agent work? Watching geometry appear on screen feels like the proof that "the AI is
really doing it". How much of that value is real?

**The principle: the value of watching is inversely proportional to how well the artifact can be
inspected.**

- Watch a **robot arm** — there is no other feedback, so watching *is* the instrument.
- Watch a **render** — pointless; you can look at the render.
- **Revit is the far end of that scale.** The artifact is a queryable database with typed
  parameters. There is nothing the process view can show that the artifact cannot show better.

So the intuition that "watching it model in Revit makes even less sense than in Blender" is correct,
and it generalizes: the more inspectable the output, the more pointless the process view.

**Four different things hide inside the word "seeing"** — they are not interchangeable, and only one
of them involves a human watching.

| | What it is | Value |
|---|---|---|
| **A human watches the process** | a screen recording of clicks | **Demonstration and teaching only.** No engineering value. |
| **A human inspects the artifact** | open the `.rfa`; read the BOQ rows | **Essential** — and already how this project works. |
| **The agent looks at the screen** | a screenshot for its own verification | **Legitimate and cheap** — this is the *agent's* perception (§7's "camera"), not a spectator sport. |
| **The audit trail** | log, diff, manifest, post-commit re-read | **Essential for diagnosis** — and strictly better than watching. |

⚠ **The audit trail beats the process view on every axis that matters.** It is repeatable, searchable
and diffable, and it does not consume a human's attention while it runs. A video is none of those.
This is the same conclusion the engine already reached: the takeoff does not ask you to believe it,
it prints the rows.

**Where watching does retain value** — the honest list, since the value is real but narrow:

1. **Demonstration to a buyer.** A commercial product has to be shown. ⚠ But the stronger sales
   artifact available here is **a script that produces a priced BOQ in seconds** — it shows the
   *result*, which is what a QS firm actually buys.
2. **Teaching a human the tool.** Watching the loop once is a decent tutorial.
3. **Debugging a vision agent's perception.** You need the screenshot to know what the model saw.
   Irrelevant if the agent does not use vision.

None of the three is an engineering requirement, and none is a reason to build a GUI-driving agent.

**The loop the artifact actually enables:**

```
  agent ──produces──▶  family.rfa  ──human opens, inspects──▶  verdict
                          ▲                                      │
                          └─────────  "adjust it"  ◀─────────────┘
```

⚠⚠ **The hazard: which is the source of truth — the script or the file?** A generated `.rfa` is a
**build output**. If the agent edits the file directly and the script is later re-run, the edits are
clobbered. **This is the same class of problem `MASTER_SYSTEM_SPEC.md` §3 was written to kill for
the docs** — one artifact, several copies, no declared authority. Decide it explicitly for families
too, before it bites.

⚠ **A `.rfa` is a binary blob — you cannot diff it.** So "the artifact is the interface" works for
*inspection* but not for *regression detection*. What **is** diffable is the **parameter table**.

**Recommendation — make the artifact self-reporting.** Rather than "open it and look", have the
agent emit a **manifest** alongside the file: type and instance parameters, bounding extents,
element counts, warnings. Then inspection is a *table* — comparable across runs, diffable, and
cheap — and manually opening the file becomes the *confirmation* rather than the primary check.

---

## Sources

- OSWorld benchmark analysis and the long-horizon finding: `agentmarketcap.ai/blog/2026/04/10/computer-use-benchmark-guide-osworld-appagent-androidworld-webagent`
- OSWorld 2026 scores (vendor blog — self-reported, treated with caution): `coasty.ai/blog/osworld-benchmark-2026-computer-use-agents-ranked`
- `vahidrahimiarchitect/Revit-AI-BIM-Agent-claude` — the "canvas" marketing vs the API architecture: `github.com/vahidrahimiarchitect/Revit-AI-BIM-Agent-claude`
- Field survey and the `ExternalEvent` threading constraint: `REVIT_MCP_LANDSCAPE.md` §§2–3
- Computer use explained (screenshot → plan → inject input): `aiho.net/wiki/computer-use.html`
- API gap register: `REVIT_MCP_LANDSCAPE.md` §3.7
