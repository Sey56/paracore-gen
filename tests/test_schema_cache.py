"""Tests for mcp_core.schema_cache — the parameter-name rendering.

⚠ These exist because the schema told the caller to "COPY THE EXACT NAME" while printing a
name that does not resolve: `GetStr("Level [Reference]")` returns "" on the live model and
warns. Measured 2026-10-27 against TestModel.rvt.
"""

# ── the SHARED MCP CORE (`paracore/mcp`) — put it on sys.path ────────────────
import os as _os
import sys as _sys

if not getattr(_sys, "frozen", False):
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _dir, _core = _here, None
    for _ in range(6):
        if _os.path.isfile(_os.path.join(_dir, "paracore", "mcp", "mcp_core", "__init__.py")):
            _core = _os.path.join(_dir, "paracore", "mcp")
            break
        _up = _os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(
            "Paracore MCP shared core not found: no `paracore/mcp/mcp_core` above "
            f"{_here}. The core lives in the ENGINE repo, so the repos must be SIBLING "
            "checkouts under one parent directory."
        )
    _sys.path.insert(0, _core)

from mcp_core.schema_cache import base_parameter_name, search_schema, _cache


def _with_params(category, params):
    """Run a body against a stubbed cache, then restore it."""
    saved = dict(_cache)
    _cache.clear()
    _cache[category] = params
    try:
        return search_schema(category)
    finally:
        _cache.clear()
        _cache.update(saved)


class TestBaseParameterName:
    def test_strips_the_reference_annotation(self):
        assert base_parameter_name("Level [Reference]") == "Level"

    def test_strips_a_storage_annotation(self):
        assert base_parameter_name("Frame Material [String]") == "Frame Material"
        assert base_parameter_name("Area [Double]") == "Area"

    def test_leaves_a_plain_name(self):
        assert base_parameter_name("Fire Rating") == "Fire Rating"
        assert base_parameter_name("IfcGUID") == "IfcGUID"

    def test_leaves_an_unknown_bracket_suffix(self):
        # Not a known annotation token -> must not be touched.
        assert base_parameter_name("Odd [Custom]") == "Odd [Custom]"

    def test_handles_empty(self):
        assert base_parameter_name("") == ""


class TestSearchSchemaRendering:
    def test_never_prints_a_bracketed_annotation(self):
        text = _with_params("Doors", [
            {"name": "Level [Reference]", "storage_type": "ElementId", "is_type": False},
        ])
        assert "[Reference]" not in text
        assert "`Level`" in text

    def test_collapses_rows_that_are_identical(self):
        """Two parameters with the same name, storage and scope are one line.

        ⚠ Measured on Doors: `Level [Reference]` appeared TWICE, identically. A second
        identical line teaches the agent nothing and reads as a bug in this tool.
        """
        text = _with_params("Doors", [
            {"name": "Level [Reference]", "storage_type": "ElementId", "is_type": False},
            {"name": "Level [Reference]", "storage_type": "ElementId", "is_type": False},
        ])
        assert text.count("- `Level`") == 1
        assert "1 parameters" in text

    def test_keeps_rows_that_differ_in_storage_or_scope(self):
        """`Frame Material` is genuinely two parameters — that difference must survive."""
        text = _with_params("Doors", [
            {"name": "Frame Material [Reference]", "storage_type": "ElementId", "is_type": True},
            {"name": "Frame Material [String]", "storage_type": "String", "is_type": False},
        ])
        assert text.count("- `Frame Material`") == 2
        assert "2 parameters" in text

    def test_instruction_says_the_backticked_text(self):
        text = _with_params("Doors", [
            {"name": "Comments", "storage_type": "String", "is_type": False},
        ])
        assert "in backticks" in text


# ── The usage example must be built from the rows above it ───────────────────
# ⚠⚠ WHY (2026-10-27, review round 5). The example was a fixed template naming `Level`
#   and `Name`. `Level` is right for Rooms/Doors/Windows and does not exist on Walls
#   (62 parameters; the nearest is `Base Constraint`). `GetStr` on a missing name returns
#   "" with no error, so the advice compiled, ran, and produced a column of blanks —
#   the silent-empty-column failure the instructions warn about, shipped AS the advice.
class TestUsageExample:
    def _example(self, category, rows):
        from mcp_core.tools import _schema_usage_example
        return _schema_usage_example(category, rows)

    @staticmethod
    def _names(text):
        """Every parameter name the example actually queries."""
        import re
        return set(re.findall(r'Get(?:Str|Num)\("([^"]+)"', text)) | set(
            re.findall(r'GroupByParam\("([^"]+)"', text))

    def test_example_only_names_parameters_in_the_rows(self):
        rows = [
            {"name": "Base Constraint", "storage": "ElementId", "scope": "Instance"},
            {"name": "Area", "storage": "Double", "scope": "Instance"},
            {"name": "Comments", "storage": "String", "scope": "Instance"},
        ]
        text = self._example("Walls", rows)
        assert self._names(text) <= {r["name"] for r in rows}

    def test_walls_never_get_the_level_parameter(self):
        """The regression itself: Walls have no `Level`."""
        rows = [
            {"name": "Base Constraint", "storage": "ElementId", "scope": "Instance"},
            {"name": "Area", "storage": "Double", "scope": "Instance"},
        ]
        text = self._example("Walls", rows)
        assert '"Level"' not in text

    def test_the_unit_matches_the_parameter(self):
        """`GetNum(name, "m2")` converts silently even on a non-area — see tools.py."""
        rows = [
            {"name": "Comments", "storage": "String", "scope": "Instance"},
            {"name": "Perimeter", "storage": "Double", "scope": "Instance"},
        ]
        text = self._example("Structural Columns", rows)
        assert 'GetNum("Perimeter", "m")' in text

    def test_a_numeric_parameter_with_no_known_unit_gets_no_unit(self):
        rows = [
            {"name": "Comments", "storage": "String", "scope": "Instance"},
            {"name": "Absorptance", "storage": "Double", "scope": "Instance"},
        ]
        text = self._example("Walls", rows)
        assert "Absorptance" not in text      # not in the preference list -> omitted
        assert "GetNum" not in text

    def test_id_is_value_never_integervalue(self):
        rows = [{"name": "Comments", "storage": "String", "scope": "Instance"}]
        text = self._example("Walls", rows)
        assert "e.Id.Value" in text
        assert "IntegerValue" not in text

    def test_a_column_name_is_a_legal_csharp_identifier(self):
        from mcp_core.tools import _csharp_identifier
        assert _csharp_identifier("Base Constraint") == "Base_Constraint"
        assert _csharp_identifier("Heat Transfer Coefficient (U)") == "Heat_Transfer_Coefficient_U"
        assert _csharp_identifier("3D") == "_3D"
        assert _csharp_identifier("") == "_"


class TestNoSchemaMeansNoExample:
    def test_a_failed_category_prints_no_usage_block(self, monkeypatch):
        """⚠ Hermetic on purpose: `_fetch_category_params` is stubbed to "not found", so
        this proves the GUARD rather than whatever model happens to be open."""
        import mcp_core.schema_cache as sc
        from mcp_core.tools import search_schema as tool

        monkeypatch.setattr(sc, "_fetch_category_params", lambda name: [])
        sc.clear_cache()
        try:
            out = tool("Banana Peels")
        finally:
            sc.clear_cache()
        assert out.startswith("No parameters found")
        assert "To query" not in out
