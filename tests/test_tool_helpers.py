"""Tests for mcp_core.tool_helpers — pure functions, no mocking needed."""


# ── the SHARED MCP CORE (`paracore/mcp`) — put it on sys.path ────────────────
# ⚠ It is not a per-repo package any more: it lives ONCE in the ENGINE repo and every MCP
#   imports it. See paracore/mcp/mcp_core/domain.py. Walk up to the sibling checkout.
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
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mcp_core.tool_helpers import (
    sanitize_csharp_code,
    check_paracore_compliance,
    check_dangerous_patterns,
    check_suspicious_param_names,
    check_read_only_violation,
    check_agent_file_policy,
    lint_paracore_conventions,
    _suggest_paracore_fix,
)


# ── sanitize_csharp_code ──────────────────────────────────────────────────

class TestSanitize:
    def test_strips_bracket_annotations(self):
        assert sanitize_csharp_code('"Level [String]"') == '"Level"'
        assert sanitize_csharp_code('"Area [Double]"') == '"Area"'
        assert sanitize_csharp_code('"Volume [Double]"') == '"Volume"'

    def test_strips_paren_annotations(self):
        assert sanitize_csharp_code('"Level (String)"') == '"Level"'

    def test_preserves_valid_strings(self):
        assert sanitize_csharp_code('"Fire Rating"') == '"Fire Rating"'
        assert sanitize_csharp_code('"Level"') == '"Level"'

    def test_handles_multiple_annotations(self):
        code = '.WhereParam("Level [String]", "Level 1").GetNum("Area [Double]", "m2")'
        result = sanitize_csharp_code(code)
        assert '"Level [String]"' not in result
        assert '"Area [Double]"' not in result
        assert '"Level"' in result
        assert '"Area"' in result

    def test_strips_the_reference_annotation(self):
        """⚠ An add-in built before 2026-10-27 disambiguated a colliding parameter name by
        appending its storage type. "Reference" is NOT a storage type and NOT part of the
        name — GetStr("Level [Reference]") returns "" on the live model and warns. An agent
        told to "COPY THE EXACT NAME" therefore copied a name that cannot resolve."""
        assert sanitize_csharp_code('"Level [Reference]"') == '"Level"'
        assert sanitize_csharp_code('"Frame Material [Reference]"') == '"Frame Material"'

    def test_leaves_an_unknown_bracket_suffix_alone(self):
        """Only a KNOWN annotation token is stripped. A real name ending in brackets must
        survive — silently renaming a parameter is the failure this whole fix is about."""
        assert sanitize_csharp_code('"Weird [Custom]"') == '"Weird [Custom]"'


# ── check_paracore_compliance ─────────────────────────────────────────────

class TestParacoreLayers:
    """The two layers, kept apart on purpose.

    ⚠⚠ `check_paracore_compliance` BLOCKS only what cannot run. Style and convention
    live in `lint_paracore_conventions`, which never blocks. The split is deliberate:
    a blocking rule that fires on correct code costs a round trip the caller cannot
    argue with. Eight tests here asserted the OLD regime — that `new
    FilteredElementCollector` and `.LookupParameter` were refused — and had been RED
    since the split. They now assert the behaviour that actually ships, and each one
    also asserts the code is NOT blocked, so nobody can re-tighten the blocking layer
    without a test going red. (Measured 2026-10-27: this is the same stale claim that
    the `ping` cheat-sheet was making with "FORBIDDEN … will be REJECTED".)
    """

    def test_flags_filtered_element_collector(self):
        code = "new FilteredElementCollector(Doc)"
        lint = lint_paracore_conventions(code)
        assert lint is not None and "GetElements" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_flags_lookup_parameter(self):
        code = 'el.LookupParameter("Name")'
        lint = lint_paracore_conventions(code)
        assert lint is not None and "GetStr" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_flags_get_parameter(self):
        code = 'el.get_Parameter("Name")'
        lint = lint_paracore_conventions(code)
        assert lint is not None and "GetStr" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_flags_console_writeline(self):
        code = "Console.WriteLine(msg)"
        lint = lint_paracore_conventions(code)
        assert lint is not None and "Println" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_flags_foreach_println(self):
        # ⚠ The pattern deliberately requires 3+ Println calls in one loop body:
        # "only flag when used as the PRIMARY display method ... not when used for
        # quick debug checks". A 1-Println body is a legitimate debug loop and must
        # stay silent. Measured: 1 Println -> silent, 2 -> silent, 3 -> fires.
        code = ('foreach(var x in items) { Println(x.Name); Println(x.Id); '
                'Println(x.Level); }')
        lint = lint_paracore_conventions(code)
        assert lint is not None and "Table" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_allows_a_one_println_debug_loop(self):
        # The other half of the same rule: do not nag on a quick debug loop.
        code = 'foreach(var x in items) { Println(x.Name); }'
        assert lint_paracore_conventions(code) is None
        assert check_paracore_compliance(code) is None

    def test_blocks_select_after_groupbyparam(self):
        err = check_paracore_compliance(
            'GetElements("Walls").GroupByParam("Level").Select(g => new{})'
        )
        assert err is not None
        assert "Table" in err

    def test_flags_hardcoded_unit_math(self):
        code = "var x = value / 304.8;"
        lint = lint_paracore_conventions(code)
        assert lint is not None and "unit" in lint.lower()
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_blocks_lowercase_doc(self):
        err = check_paracore_compliance("doc.ProjectInformation")
        assert err is not None
        assert "Doc" in err

    def test_flags_orderby_lambda(self):
        code = "elements.OrderBy(e => e.GetNum(\"Area\"))"
        lint = lint_paracore_conventions(code)
        assert lint is not None and "OrderByParam" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_flags_sum_lambda(self):
        code = "elements.Sum(e => e.GetNum(\"Area\", \"m2\"))"
        lint = lint_paracore_conventions(code)
        assert lint is not None and "SumParam" in lint
        assert check_paracore_compliance(code) is None, "style must not block"

    def test_blocks_transact_without_name(self):
        err = check_paracore_compliance("Transact(() => { wall.Delete(); })")
        assert err is not None
        assert "name string" in err.lower()

    def test_blocks_combinedparams_with_args(self):
        err = check_paracore_compliance(
            'el.CombinedParams("filter").Table()'
        )
        assert err is not None
        assert "NO arguments" in err

    def test_blocks_setval_on_collection(self):
        err = check_paracore_compliance(
            'GetElements("Walls").WhereParam("Fire Rating","None").SetVal("Comments","X")'
        )
        assert err is not None

    def test_allows_valid_code(self):
        assert check_paracore_compliance(
            'GetElements("Walls").WhereParam("Fire Rating", "2 hr").Table()'
        ) is None

    def test_allows_getstr_getnum(self):
        assert check_paracore_compliance(
            'el.GetStr("Name"); el.GetNum("Area", "m2")'
        ) is None

    def test_allows_groupbyparam_then_table(self):
        assert check_paracore_compliance(
            'GetElements("Walls").GroupByParam("Level").Table()'
        ) is None


# ── check_dangerous_patterns ──────────────────────────────────────────────

class TestDangerousPatterns:
    def test_blocks_process_start(self):
        err = check_dangerous_patterns("Process.Start(\"cmd.exe\")")
        assert err is not None
        assert "Process.Start" in err

    def test_blocks_environment_exit(self):
        err = check_dangerous_patterns("Environment.Exit(0)")
        assert err is not None

    def test_blocks_registry_access(self):
        err = check_dangerous_patterns("Microsoft.Win32.Registry")
        assert err is not None

    def test_blocks_assembly_load(self):
        err = check_dangerous_patterns("Assembly.Load(byteArray)")
        assert err is not None

    def test_blocks_file_delete(self):
        err = check_dangerous_patterns("File.Delete(\"test.txt\")")
        assert err is not None

    def test_blocks_httpclient_agent_only(self):
        err = check_dangerous_patterns("new HttpClient()", agent_only=True)
        assert err is not None
        # ⚠ This used to assert "RestSharp" — the old message redirected the agent from
        #   HttpClient to another network client. Network is off for agent code now.
        assert "network" in err.lower()
        assert "RestSharp" not in err

    def test_allows_httpclient_when_not_agent(self):
        assert check_dangerous_patterns("new HttpClient()", agent_only=False) is None

    def test_allows_safe_code(self):
        assert check_dangerous_patterns(
            'GetElements("Walls").Table()'
        ) is None


# ── check_suspicious_param_names ──────────────────────────────────────────

class TestSuspiciousParamNames:
    def test_flags_fabricated_pascalcase(self):
        # Not in any schema cache — should warn
        warn = check_suspicious_param_names(
            'GetElements("Walls").WhereParam("FireRating", "2 hr")'
        )
        assert "FireRating" in warn
        assert "no spaces" in warn.lower()

    def test_passes_single_word_params(self):
        assert check_suspicious_param_names('GetNum("Volume", "m3")') == ""
        assert check_suspicious_param_names('GetStr("Mark")') == ""
        assert check_suspicious_param_names('GetStr("Length")') == ""

    def test_passes_space_separated_params(self):
        assert check_suspicious_param_names(
            'WhereParam("Fire Rating", "2 hr")'
        ) == ""

    def test_silences_if_in_schema_cache(self):
        from mcp_core.schema_cache import _cache as schema_cache
        # Populate cache with a known PascalCase param
        schema_cache["Doors"] = [
            {"name": "IfcGUID", "storage_type": "String", "is_type": False},
            {"name": "StopDepth", "storage_type": "Double", "is_type": True},
        ]
        warn = check_suspicious_param_names(
            'GetElements("Doors").GetStr("IfcGUID")'
        )
        assert warn == ""  # silently passes — it's a real param

    def test_returns_empty_for_no_quoted_strings(self):
        assert check_suspicious_param_names("var x = 5;") == ""


# ── _suggest_paracore_fix ─────────────────────────────────────────────────

class TestSuggestParacoreFix:
    def test_suggests_whereparam_for_where_error(self):
        suggestion = _suggest_paracore_fix(
            "does not contain a definition for 'Where'"
        )
        assert suggestion is not None
        assert "WhereParam" in suggestion

    def test_suggests_orderbyparam_for_orderby_error(self):
        suggestion = _suggest_paracore_fix(
            "does not contain a definition for 'OrderBy'"
        )
        assert suggestion is not None
        assert "OrderByParam" in suggestion

    def test_suggests_getstr_for_lookupparameter_error(self):
        suggestion = _suggest_paracore_fix(
            "'LookupParameter' is not"
        )
        assert suggestion is not None
        assert "GetStr" in suggestion

    def test_suggests_doc_for_lowercase_doc_error(self):
        suggestion = _suggest_paracore_fix(
            "The name 'doc' does not exist"
        )
        assert suggestion is not None
        assert "Doc" in suggestion

    def test_suggests_getelements_for_filteredelementcollector(self):
        suggestion = _suggest_paracore_fix(
            "FilteredElementCollector is not"
        )
        assert suggestion is not None
        assert "GetElements" in suggestion

    def test_suggests_println_for_console_error(self):
        suggestion = _suggest_paracore_fix("'Console' does not exist")
        assert suggestion is not None
        assert "Println" in suggestion

    def test_maps_multiple_suggestions(self):
        suggestion = _suggest_paracore_fix(
            "does not contain a definition for 'Where' and 'OrderBy'"
        )
        assert suggestion is not None
        assert "WhereParam" in suggestion or "OrderByParam" in suggestion

    def test_returns_none_for_unknown_error(self):
        assert _suggest_paracore_fix("some random error text") is None


# ── Read-only guard (explore_revit_data) ─────────────────────────────────────
# ⚠⚠ THE REGRESSION THIS LOCKS DOWN (2026-10-27): a pre-release review ran, LIVE, a
#    snippet of `new Transaction(Doc, ...)` + `Parameter.Set(...)` through
#    explore_revit_data and it EXECUTED. So did `Doc.Delete(id)`. The engine's own gate
#    (Paracore.Addin/Handlers/ReplHandler.cs) scans for `.Delete()` with EMPTY parens and
#    for `Transact(`, so neither snippet matched. Both are refused now.
# ⚠ The blind spots at the end are pinned as ACCEPTED behaviour: the guard is a
#   mistake-catcher, not a sandbox, and the test file is where that claim is kept honest.
class TestReadOnlyGuard:
    def test_refuses_raw_transaction_and_parameter_set(self):
        code = (
            'var t = new Transaction(Doc, "peek");\n'
            "t.Start();\n"
            'var p = GetElements("Walls").First().LookupParameter("Comments");\n'
            "p.Set(p.AsString());\n"
            "t.Commit();\n"
        )
        result = check_read_only_violation(code)
        assert result is not None
        assert "Transaction" in result

    def test_refuses_raw_doc_delete(self):
        # `.Delete()` — the engine's pattern — does NOT match `Doc.Delete(id)`.
        assert check_read_only_violation(
            'Doc.Delete(GetElements("Walls").First().Id);') is not None

    def test_refusal_says_the_write_is_discarded(self):
        """The message must not read as though the scan were the only layer.

        ⚠ Since 2026-10-27 the engine also runs the snippet inside a TransactionGroup that
        is ALWAYS rolled back, so a write the scan cannot see is discarded by Revit. The
        agent has to know that: routing around the scan now yields a success and an
        UNCHANGED model, which is worse than the refusal.
        """
        msg = check_read_only_violation('new Transaction(Doc, "x");')
        assert msg is not None
        assert "ALWAYS rolled back" in msg
        assert "reflection" in msg

    def test_refuses_creation(self):
        assert check_read_only_violation(
            'Wall.Create(Doc, line, lvl.Id, false);') is not None
        assert check_read_only_violation(
            'Doc.Create.NewFamilyInstance(p, sym, lvl, XYZ.Zero);') is not None

    def test_allows_a_normal_read(self):
        assert check_read_only_violation(
            'GetElements("Walls").GroupByParam("Type Name").Table();') is None

    def test_allows_every_read_snippet_in_the_skills(self):
        """The skills are the code the agent is TOLD to write — none may be refused.

        ⚠ create-geometry and write-modify are EXCLUDED on purpose: their snippets
        create and modify by definition, so refusing them is the guard working. The
        first version of this test labelled create-geometry a read skill and reported
        four "false positives" that were all real `Wall.Create` / `NewFamilyInstance`
        calls — the label was wrong, not the guard.
        """
        import re
        from pathlib import Path
        from mcp_core.domain import SHARED_SKILLS_DIR

        write_skills = {"create-geometry", "write-modify"}
        fence = re.compile(r"```csharp\s*\n(.*?)```", re.DOTALL)

        scanned = 0
        refused = []
        for skill in sorted(Path(SHARED_SKILLS_DIR).iterdir()):
            md = skill / "SKILL.md"
            if not md.is_file() or skill.name in write_skills:
                continue
            for block in fence.findall(md.read_text(encoding="utf-8")):
                scanned += 1
                if check_read_only_violation(block):
                    refused.append(f"{skill.name}: {block.strip().splitlines()[0][:60]}")

        assert scanned >= 30, f"only {scanned} snippets found — the corpus went missing"
        assert not refused, "legitimate reads refused:/n" + "\n".join(refused)

    # ── Accepted blind spots — pinned so nobody re-reads them as oversights ──
    def test_blind_spot_reflection_is_not_caught(self):
        """Exploration legitimately uses reflection to discover properties."""
        assert check_read_only_violation(
            'typeof(Parameter).GetMethod("Set").Invoke(p, new object[] { "x" });') is None

    def test_blind_spot_os_access_is_not_caught(self):
        """`System` and `System.IO` are PRE-IMPORTED for scripts — no `using` needed."""
        assert check_read_only_violation(
            'Println(Environment.UserName + Directory.Exists("C:/"));') is None

    def test_guard_is_wired_into_explore_only(self):
        """The WRITE tool must not carry this guard, or every write is refused."""
        import inspect
        from mcp_core import tools

        assert "check_read_only_violation" in inspect.getsource(tools.explore_revit_data)
        assert "check_read_only_violation" not in inspect.getsource(
            tools.execute_dynamic_query)


# ── Agent file / network policy ─────────────────────────────────────────────
# ⚠⚠ THE RULE (operator, 2026-10-27): an agent MAY create a new file and MAY read
#    files. It may NEVER replace, move or delete an existing one — "even if it is the one
#    it created earlier" — because a replace cannot tell an output from something
#    important. The user deletes files; the agent does not. Network is off.
class TestAgentFilePolicy:
    def test_refuses_every_way_to_replace_or_delete(self):
        for code in (
            'File.WriteAllText(p, text);',
            'File.WriteAllBytes(p, bytes);',
            'File.AppendAllText(p, more);',
            'File.Delete(p);',
            'Directory.Delete(d, true);',
            'File.Move(a, b);',
            'File.Replace(a, b, null);',
            'File.Copy(a, b, true);',
            'File.OpenWrite(p);',
            'using (var w = new StreamWriter(p)) { w.Write(1); }',
            'new FileStream(p, FileMode.Create)',
            'new FileStream(p, FileMode.Truncate)',
            'new FileStream(p, FileMode.Open)',
        ):
            assert check_agent_file_policy(code, "mcp_agent") is not None, code

    def test_allows_create_new_and_reads(self):
        """The blessed write path, and every read, must pass — or the rule is unusable."""
        for code in (
            'using (var fs = new FileStream(p, FileMode.CreateNew)) { fs.Write(b, 0, b.Length); }',
            'var text = File.ReadAllText(p);',
            'if (File.Exists(p)) Println("exists");',
            'var files = Directory.GetFiles(d);',
            'using (var r = new StreamReader(p)) { Println(r.ReadToEnd()); }',
        ):
            assert check_agent_file_policy(code, "mcp_agent") is None, code

    def test_filemode_createnew_is_not_mistaken_for_create(self):
        """`FileMode.Create` is a SUBSTRING of `FileMode.CreateNew` — the trap in this rule."""
        assert check_agent_file_policy(
            "new FileStream(p, FileMode.CreateNew)", "mcp_agent") is None
        assert check_agent_file_policy(
            "new FileStream(p, FileMode.Create)", "mcp_agent") is not None

    def test_manual_sources_keep_full_file_access(self):
        """A person running a gallery tool is not an agent — RoomFinishUpdater writes CSVs."""
        assert check_agent_file_policy('File.WriteAllLines(p, rows);', "paracore_ui") is None
        assert check_agent_file_policy('File.Delete(p);', "paracore") is None

    def test_refuses_network(self):
        for code in (
            'var c = new HttpClient();',
            'using RestSharp;',
            'var w = new WebClient();',
        ):
            assert check_agent_file_policy(code, "mcp_agent") is not None, code

    def test_python_policy_matches_the_addin(self):
        """⚠⚠ ANTI-DRIFT GATE — the two lists must be identical, literally.

        The Python layer gives the agent a clean refusal; the add-in is the backstop for
        a direct gRPC caller. A pattern added to one and forgotten in the other is a hole
        that neither test suite would otherwise see.
        """
        import re as _re
        from pathlib import Path
        from mcp_core.tool_helpers import _AGENT_FILE_POLICY

        cs = (Path(__file__).resolve().parents[2] / "paracore" / "Paracore.Addin"
              / "Handlers" / "ReplHandler.cs")
        assert cs.is_file(), f"add-in source not found at {cs} — the gate has no subject"
        src = cs.read_text(encoding="utf-8")

        found = _re.findall(r'\(@"((?:[^"]|"")*)",\s*"([^"]*)"\)', src)
        assert len(found) >= 20, (
            f"parsed only {len(found)} patterns from ReplHandler.cs — the C# shape changed "
            "and this gate stopped seeing its subject")

        assert found == _AGENT_FILE_POLICY, (
            "the add-in and the Python layer disagree.\n"
            f"  only in C#    : {[p for p in found if p not in _AGENT_FILE_POLICY]}\n"
            f"  only in Python: {[p for p in _AGENT_FILE_POLICY if p not in found]}")


# ── The four findings from the pre-release Claude Desktop session (2026-10-27) ──

class TestCompilerLineNumbers:
    """The engine can report +2 while CLAIMING the numbers are the user's.

    ⚠ MEASURED 2026-10-27 in a live Claude Desktop session: a missing `;` on the user's line 8
    came back as `script(10,1)` and was rendered as "engine line 10 ... outside your snippet",
    under a header that said "The engine reported these in YOUR coordinates". The 3-line
    prelude (two `using`s + `#line 1 "script"`) was still being counted, and the filename made
    the annotator trust the number.
    """

    #: 8 lines, so line 8 is the last one — the review's exact shape.
    CODE_8 = "\n".join(f"var x{i} = {i};" for i in range(1, 9))

    def test_a_batch_shifted_by_two_is_mapped_back(self):
        from mcp_core.tool_helpers import _annotate_compile_errors
        out = _annotate_compile_errors("script(10,1): error CS1002: ; expected", self.CODE_8)
        assert out is not None
        assert "your line 8" in out, out
        assert "var x8 = 8;" in out, out
        assert "not a line you wrote" not in out, out
        assert "+2" in out

    def test_a_genuinely_foreign_diagnostic_is_still_refused(self):
        from mcp_core.tool_helpers import _annotate_compile_errors
        code = "\n".join(f"var y{i} = {i};" for i in range(1, 21))
        out = _annotate_compile_errors("script(40,1): error CS1002: ; expected", code)
        assert "not a line you wrote" in out, out
        assert "20 line(s)" in out, out

    def test_correct_coordinates_are_left_alone(self):
        from mcp_core.tool_helpers import _annotate_compile_errors
        out = _annotate_compile_errors("script(3,1): error CS1002: ; expected", self.CODE_8)
        assert "your line 3" in out, out
        assert "in YOUR coordinates" in out, out


class TestBulkDetection:
    """A bulk warning that fires on a single-element call trains the agent to ignore it.

    ⚠ MEASURED 2026-10-27: `doors.First().Hide()` was reported as "bulk hide on ALL filtered
    elements". Harmless, but wrong — and a warning that fires on correct code is how the
    warnings that matter get skimmed past.
    """

    def test_a_single_element_call_is_not_bulk(self):
        from mcp_core.tools import bulk_operation_warnings
        assert bulk_operation_warnings('doors.First().Hide();') == []
        assert bulk_operation_warnings('doors.Single().Delete();') == []
        assert bulk_operation_warnings('GetElements("Doors").ElementAt(0).Hide();') == []

    def test_a_variable_holding_one_element_is_a_known_limit(self):
        """⚠ The scan cannot follow a VARIABLE: `var d = doors.First(); d.Hide();` looks
        exactly like a collection call and still warns.

        Written down rather than hidden. A false positive here is noise, which is the
        acceptable direction to be wrong in — the alternative (a silent miss on a real bulk
        delete) is the one that costs data.
        """
        from mcp_core.tools import bulk_operation_warnings
        assert bulk_operation_warnings('var d = doors.First(); d.Hide();')

    def test_a_collection_call_is_still_bulk(self):
        from mcp_core.tools import bulk_operation_warnings
        assert bulk_operation_warnings('doors.Hide();')
        assert bulk_operation_warnings('GetElements("Walls").SetParam("Mark", "W001");')
        assert bulk_operation_warnings('GetElements("Walls").WhereParam("Area", ">", 5).Delete();')

    def test_one_selector_does_not_excuse_a_second_bulk_call(self):
        from mcp_core.tools import bulk_operation_warnings
        code = 'doors.First().Hide();\nGetElements("Walls").Delete();'
        warnings = bulk_operation_warnings(code)
        # The `.Hide()` is single-element and correctly silent; the `.Delete()` over a whole
        # query is not, and must still be reported.
        assert len(warnings) == 1, warnings
        assert ".Delete()" in warnings[0]


class TestLevelLint:
    """The collector nudge must name the route that actually exists for levels.

    ⚠ The review could not confirm a typed alternative for
    `new FilteredElementCollector(Doc).OfClass(typeof(Level))`, so the nudge read as
    misleading. It is not: `GetElements<Level>()` runs `OfClass(typeof(Level))` underneath
    (ParameterOptionsComputer.CreateResilientCollector, Quirk 3). The MESSAGE just never said
    so, which is a documentation bug with the same cost as a wrong rule.
    """

    def test_the_message_names_getelements_level(self):
        from mcp_core.tool_helpers import lint_paracore_conventions
        note = lint_paracore_conventions(
            "var lvls = new FilteredElementCollector(Doc).OfClass(typeof(Level));")
        assert note is not None
        assert "GetElements<Level>()" in note, note


# ── The round-6 review's guardrail escapes (2026-10-27) ──────────────────────

class TestReviewRound6Escapes:
    """The reviewer walked past the deny-list; these pin the routes shut.

    ⚠⚠ THE POINT IS NOT THE FIVE STRINGS, IT IS THE FAMILY. The previous round refused
    `Type.GetType`, `Activator`, `.Assembly`, `GetMethod` — and the review used
    `AppDomain.GetAssemblies()` → `GetTypes()` → `GetConstructor(...).Invoke(...)` plus
    `dynamic` to make a real HTTP GET to example.com. Each test below is one step of that
    route, so a future edit that re-opens a step fails here rather than in a live session.
    """

    AGENT = "claude-agent"

    def _refused(self, code):
        """True when EITHER layer refuses it — the two run together on both tools."""
        return (check_dangerous_patterns(code, agent_only=True) is not None
                or check_agent_file_policy(code, self.AGENT) is not None)

    # ── step 1: enumerate ────────────────────────────────────────────────────
    def test_appdomain_assembly_enumeration_is_refused(self):
        code = "var asms = AppDomain.CurrentDomain.GetAssemblies();"
        assert self._refused(code)

    def test_type_enumeration_is_refused(self):
        code = "var types = typeof(object).Assembly.GetTypes();"
        assert self._refused(code)

    # ── step 2: resolve a member ─────────────────────────────────────────────
    def test_getconstructor_is_refused(self):
        code = ('var c = typeof(System.IO.File).GetConstructor(new[] { typeof(string) });')
        assert self._refused(code)

    def test_getproperty_is_refused(self):
        assert self._refused('var p = el.GetType().GetProperty("Id");')

    # ── step 3: dispatch without a symbol ────────────────────────────────────
    def test_dynamic_declaration_is_refused(self):
        assert self._refused('dynamic http = Something();')

    def test_dynamic_cast_is_refused(self):
        assert self._refused('var x = (dynamic)Something();')

    def test_cast_dynamic_on_grouped_rows_is_still_allowed(self):
        """The ONE allowed form — it is a documented recipe (aggregate-group skill)."""
        code = 'GetElements("Walls").GroupByParam("Level").Cast<dynamic>().Where(g => g.Count > 5).Table();'
        assert not self._refused(code), "Cast<dynamic>() on grouped rows must keep working"

    # ── the capability itself ────────────────────────────────────────────────
    def test_fully_qualified_httpclient_is_refused(self):
        assert self._refused('var h = new System.Net.Http.HttpClient();')

    def test_dns_and_smtp_are_refused(self):
        assert self._refused('var ip = Dns.GetHostAddresses("example.com");')
        assert self._refused('var m = new SmtpClient("mail.example.com");')

    def test_file_move_and_replace_are_refused(self):
        assert self._refused('File.Move("a.csv", "b.csv");')
        assert self._refused('File.Replace("a.csv", "b.csv", null);')

    def test_fileinfo_delete_is_refused_but_reading_it_is_not(self):
        assert self._refused('new FileInfo("a.csv").Delete();')
        assert not self._refused('var n = new FileInfo(path).Length;'), \
            "reading a file's size is allowed — only delete/move/replace is not"

    # ── the scan must read CODE, not prose ───────────────────────────────────
    def test_a_comment_naming_a_blocked_call_is_not_refused(self):
        """⚠ The engine's own docs say 'never write Process.Start'. A scan that fires on
        documentation teaches the reader to ignore the message."""
        code = (
            "// never call Process.Start() here, and no HttpClient either\n"
            'var walls = GetElements("Walls");\n'
            "Println(walls.Count());"
        )
        assert not self._refused(code)

    def test_a_string_literal_naming_a_blocked_call_is_not_refused(self):
        code = 'Println("this report explains why Process.Start() is refused");'
        assert not self._refused(code)
