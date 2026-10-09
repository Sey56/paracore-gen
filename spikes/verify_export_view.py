"""
Offline verification for the export_view tool + the project-modeling skill.

Run with the build venv, from the paracore-gen root:
    mcp-build/.venv/Scripts/python.exe spikes/verify_export_view.py

Why a script and not a REPL one-liner: importing mcp_server.py is the ONLY thing that
proves the `-> Image` return annotation survives FastMCP's decoration. A wrong
annotation raises InvalidSignature at import time, and nothing else in the tree would
catch it — py_compile certainly does not (it never evaluates annotations).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures = []
checks = 0


def check(name, cond, detail=""):
    global checks
    checks += 1
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        failures.append(name)


print("== 1. mcp_core.tools imports and exposes export_view_report ==")
from mcp_core import tools as T
check("export_view_report exists", hasattr(T, "export_view_report"))
check("_export_view_snippet exists", hasattr(T, "_export_view_snippet"))

print("\n== 2. the generated C# snippet ==")
s_active = T._export_view_snippet(r"C:\tmp\view_ab12cd34", "", 1200)
# ⚠ C#'s null literal is UNQUOTED — assert on ", null," not on '"null"'.
check("active view -> null", ", null," in s_active and "ExportImage(" in s_active, s_active)
check("active view, no Transact", "Transact" not in s_active, s_active)

s_named = T._export_view_snippet(r"C:\tmp\view_ab12cd34", '3D View - {3D}', 2000)
check("named view is quoted", '"3D View - {3D}"' in s_named, s_named)
check("verbatim path keeps backslashes", '@"C:\\tmp\\view_ab12cd34"' in s_named, s_named)
check("pixel size reaches the call", ", 2000)" in s_named, s_named)

s_quote = T._export_view_snippet(r"C:\tmp\v", 'He said "hi"', 1200)
check("embedded quote is escaped", '\\"hi\\"' in s_quote, s_quote)

print("\n== 3. mcp_server imports (the Image-annotation trap) ==")
try:
    import mcp_server as S
    check("mcp_server imported", True)
except Exception as e:
    check("mcp_server imported", False, f"{type(e).__name__}: {e}")
    print(f"\n{len(failures)} FAILURE(S) / {checks} checks")
    sys.exit(1)

print("\n== 4. export_view is a registered tool ==")
tool_names = []
try:
    for t in S.mcp._tool_manager.list_tools():
        tool_names.append(getattr(t, "name", str(t)))
except Exception as e:
    print(f"  (could not list tools: {type(e).__name__}: {e})")
check("export_view registered", "export_view" in tool_names, f"tools={tool_names}")
check("7 original tools still registered",
      all(n in tool_names for n in
          ["ping", "get_context", "pick_object", "_explore_revit_data",
           "_execute_dynamic_query", "_search_schema", "_read_extension_methods"]),
      f"tools={tool_names}")
print(f"  tools now: {sorted(tool_names)}")

print("\n== 5. project-modeling skill is registered and loads ==")
check("project-modeling in _SKILL_DESCRIPTIONS", "project-modeling" in S._SKILL_DESCRIPTIONS)
body = S._SKILL_CACHE.get("project-modeling", "")
check("skill body loaded (not 'Skill not found')",
      "Skill not found" not in body and len(body) > 2000, f"{len(body)} chars")
check("skill routes away from massing", "cannot become" in body)
check("skill has the closure-validation trap", "closure gap" in body)
check("skill has Doc.GetWarnings", "Doc.GetWarnings()" in body)

print("\n== 6. routing fixes reached the other skills ==")
mass = S._SKILL_CACHE.get("massing-forms", "")
check("massing-forms says CONCEPT STUDIES ONLY", "CONCEPT STUDIES ONLY" in mass)
cg = S._SKILL_CACHE.get("create-geometry", "")
check("create-geometry points to project-modeling", "project-modeling" in cg)
dv = S._SKILL_CACHE.get("display-visualize", "")
check("display-visualize documents export_view", "export_view(" in dv)
check("display-visualize keeps ExportImage", "ExportImage(" in dv)

print("\n== 7. the server instructions carry the modelling routing rule ==")
instr = S.mcp.instructions or ""
check("instructions mention project-modeling", "project-modeling" in instr)
check("instructions warn off massing", "cannot become a wall" in instr)

print(f"\n{'=' * 60}")
print(f"{checks - len(failures)}/{checks} checks passed")
if failures:
    print("FAILURES: " + ", ".join(failures))
    sys.exit(1)
print("ALL CHECKS PASSED")
