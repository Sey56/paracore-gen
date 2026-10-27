"""Gate: every reference a skill makes must RESOLVE.

WHY THIS EXISTS
    The pre-release review found `create-geometry` telling the reader to run
    `read_skill("project-modeling")` — a skill that lives in a different product and is not
    in this server's catalogue. The call fails, and a public user has no way to know the
    recipe was never here.

    ⚠ The failure mode is SILENT in every other check we have: a skill is prose, nothing
    compiles it, and `read_skill` answers an unknown name politely with a list. So the gate
    is a scan for the CLASS of defect — a name written in one file that does not exist in
    another — not a check for the one string that was found this time. Anchors rot; the
    class does not.
"""

import os
import re
import sys

import pytest

# ── the SHARED MCP CORE (`paracore/mcp`) — put it on sys.path ────────────────
if not getattr(sys, "frozen", False):
    _here = os.path.dirname(os.path.abspath(__file__))
    _dir, _core = _here, None
    for _ in range(6):
        if os.path.isfile(os.path.join(_dir, "paracore", "mcp", "mcp_core", "__init__.py")):
            _core = os.path.join(_dir, "paracore", "mcp")
            break
        _up = os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(f"shared MCP core not found above {_here}")
    sys.path.insert(0, _core)

from mcp_core.domain import (  # noqa: E402
    Domain, SHARED_PROMPTS_DIR, SHARED_SKILLS_DIR, skill_catalogue,
)

ROOT = os.path.dirname(_here)
DOMAIN = Domain(name="Gate", slug="gate", intro="", root=ROOT)


def _skill_files():
    for name in sorted(os.listdir(SHARED_SKILLS_DIR)):
        path = os.path.join(SHARED_SKILLS_DIR, name, "SKILL.md")
        if os.path.isfile(path):
            yield name, path


def _prompt_files():
    for name in sorted(os.listdir(SHARED_PROMPTS_DIR)):
        if name.endswith(".md"):
            yield name, os.path.join(SHARED_PROMPTS_DIR, name)


def _catalogue_names():
    return {s.name for s in skill_catalogue(DOMAIN)}


# Products this repo does NOT ship. A public reader cannot obtain them, so a pointer to
# one is a dead end — not a hint.
FOREIGN_PRODUCTS = (
    "paracore-model", "paracore-family", "paracore-pro",
    "project-modeling", "family-authoring", "massing-forms",
)


class TestSkillCatalogue:
    def test_every_directory_is_catalogued(self):
        on_disk = {name for name, _ in _skill_files()}
        assert on_disk == _catalogue_names(), (
            "a skill directory and the served catalogue disagree — "
            "`read_skill` would serve something `list_skills` never advertised, or advertise "
            "something it cannot open"
        )

    def test_every_frontmatter_name_matches_its_directory(self):
        """⚠ `read_skill` loads `<dir>/SKILL.md` by NAME, so a drifted frontmatter is cosmetic
        — but the catalogue description is keyed by the directory, and a reader trusts the
        heading. They must agree."""
        for dirname, path in _skill_files():
            with open(path, encoding="utf-8") as fh:
                head = fh.read(400)
            m = re.search(r"^name:\s*(\S+)\s*$", head, re.MULTILINE)
            assert m, f"{dirname}/SKILL.md has no `name:` in its frontmatter"
            assert m.group(1) == dirname, (
                f"{dirname}/SKILL.md declares name: {m.group(1)}"
            )


class TestReferencesResolve:
    def test_a_mentioned_skill_exists(self):
        known = _catalogue_names()
        for dirname, path in _skill_files():
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for mentioned in re.findall(r'read_skill\(\s*["\']([^"\']+)["\']', text):
                assert mentioned in known, (
                    f"{dirname} tells the reader to run read_skill({mentioned!r}), which is "
                    f"not in this catalogue: {sorted(known)}"
                )

    def test_no_foreign_product_is_referenced(self):
        for dirname, path in _skill_files():
            with open(path, encoding="utf-8") as fh:
                text = fh.read().lower()
            for foreign in FOREIGN_PRODUCTS:
                assert foreign not in text, (
                    f"{dirname} points at {foreign!r} — this server does not ship it, and a "
                    "public reader cannot obtain it. Teach the recipe here or drop the pointer."
                )

    def test_no_resource_pointer(self):
        """⚠ Resources are INERT on the clients this server targets (0 `resources/read` in 70
        Claude Desktop sessions — see mcp_core/domain.py). A `paracore://` pointer is a dead
        end, so guidance must name a TOOL."""
        for dirname, path in list(_skill_files()) + list(_prompt_files()):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            assert "paracore://" not in text, (
                f"{dirname} points at a resource the caller cannot open"
            )


class TestNoDeveloperNotes:
    """The review found internal working notes in text that ships to every user."""

    BANNED = (
        (r"\b\d{4}-\d{2}-\d{2}\b", "a dated working note"),
        (r"\bhouse model\b", "an internal model name"),
        (r"\bBirr\b", "a private example value"),
    )

    def test_no_dated_or_private_notes(self):
        for dirname, path in list(_skill_files()) + list(_prompt_files()):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for pattern, what in self.BANNED:
                hit = re.search(pattern, text, re.IGNORECASE)
                assert not hit, f"{dirname} contains {what}: {hit.group(0)!r}"


class TestLiveInstructions:
    """Gate the text the model ACTUALLY receives — `instructions=`, the handshake string.

    ⚠⚠ WHY THIS CLASS EXISTS (2026-10-27). `create-geometry` was corrected to stop pointing
    at `paracore-model` / `paracore-family`, and every check above went green — because they
    all scan SKILL files and the `prompts/` directory. The SAME dead pointer was still in
    `mcp_server.GEN_INTRO`, which is not a skill and not a prompt file: it is the one block
    concatenated into `build_instructions()` and delivered on every session. The gates were
    green and the defect shipped in the most-read text in the product.

    So this scans the DELIVERED string, not the sources that feed it. A rule is only
    enforced where the reader meets it.
    """

    @staticmethod
    def _live() -> str:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        import mcp_server  # imported lazily: builds the server, which the other gates do not need
        return mcp_server.mcp.instructions or ""

    def test_the_scan_is_not_empty(self):
        """An EMPTY scan must FAIL — otherwise this class passes on a server that sends
        nothing at all, which is the failure mode it exists to catch."""
        live = self._live()
        assert len(live) > 1000, (
            f"the live instructions are only {len(live)} chars — the scan below would pass "
            "vacuously"
        )
        assert "GENERALIST" in live

    def test_no_foreign_product_in_the_live_instructions(self):
        live = self._live().lower()
        for foreign in FOREIGN_PRODUCTS:
            assert foreign not in live, (
                f"the live instructions point at {foreign!r} — this server does not ship it. "
                "This is the text every session starts with; a dead end here is the worst "
                "place for one."
            )

    def test_no_resource_pointer_in_the_live_instructions(self):
        assert "paracore://" not in self._live(), (
            "the live instructions name a resource URI — resources are never read by the "
            "clients this server targets (see mcp_core/domain.py); name a TOOL instead"
        )

    def test_every_skill_it_names_is_catalogued(self):
        known = _catalogue_names()
        for mentioned in re.findall(r'read_skill\(\s*["\']([^"\']+)["\']', self._live()):
            # `read_skill("<name>")` is the shape of the CALL, not a name — COMMON_RULES uses
            # the angle brackets to show the form. Only literal names are checked.
            if "<" in mentioned or ">" in mentioned:
                continue
            assert mentioned in known, (
                f"the live instructions say read_skill({mentioned!r}), which is not in this "
                f"catalogue: {sorted(known)}"
            )


class TestGeneralistScope:
    """Gate the operator's ruling: **`paracore-model` is what models.**

    ⚠⚠ WHY THIS EXISTS (2026-10-27). `paracore-gen` is the GENERALIST: it does its job by
    generating REPL on the fly, with full access to the raw Revit API, LINQ and the DSL, and
    `GEN_INTRO` states which to prefer. It is not a modelling server, so it must not carry a
    modelling curriculum — `create-geometry` is filtered out of its catalogue.

    ⚠ The two halves are asserted TOGETHER on purpose: the skill must be ABSENT from gen's
    catalogue and STILL PRESENT in the shared core. Deleting the file would "fix" this gate
    while silently breaking `paracore-model`, which is the server that models.
    """

    METHOD_ONLY = {
        "query-filter", "aggregate-group", "parameter-access", "write-modify",
        "display-visualize", "discovery-debug", "identity-orientation", "materials-units",
    }

    @staticmethod
    def _served() -> set:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        import mcp_server
        from mcp_core.domain import skill_catalogue
        return {s.name for s in skill_catalogue(mcp_server.DOMAIN)}

    def test_gen_serves_the_eight_non_modelling_skills(self):
        assert self._served() == self.METHOD_ONLY, (
            "gen's skill set changed. It is the generalist: the eight shared METHOD skills and "
            "nothing else. If you are adding a skill here, it belongs in paracore-model."
        )

    def test_gen_does_not_teach_modelling(self):
        assert "create-geometry" not in self._served()

    def test_gen_cannot_read_the_modelling_skill(self):
        """The catalogue filter and `read_skill` must AGREE — advertising a skill you cannot
        open, or opening one you never advertised, both make `list_skills` a lie."""
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        import mcp_server
        from mcp_core.domain import load_skill_text
        assert load_skill_text(mcp_server.DOMAIN, "create-geometry") is None

    def test_the_modelling_skill_still_exists_for_the_servers_that_model(self):
        path = os.path.join(SHARED_SKILLS_DIR, "create-geometry", "SKILL.md")
        assert os.path.isfile(path), (
            "create-geometry/SKILL.md was DELETED — gen filtering it out is correct, but "
            "paracore-model needs the file. Remove it from gen's Domain, never from the core."
        )
