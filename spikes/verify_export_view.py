"""
Offline verification for the export_view tool + the generalist skill set.

Run with the build venv, from the paracore-gen root:
    mcp-build/.venv/Scripts/python.exe spikes/verify_export_view.py

Why a script and not a REPL one-liner: importing mcp_server.py is the ONLY thing that
proves the `-> Image` return annotation survives FastMCP's decoration. A wrong
annotation raises InvalidSignature at import time, and nothing else in the tree would
catch it — py_compile certainly does not (it never evaluates annotations).
"""


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
check("_export_view_tags_snippet exists", hasattr(T, "_export_view_tags_snippet"))

print("\n== 2. the generated C# snippet ==")
# ⚠ _export_view_snippet gained `hide_annotation` with the annotations modes (2026-10-08).
s_active = T._export_view_snippet(r"C:\tmp\view_ab12cd34", "", 1200, True)
# ⚠ C#'s null literal is UNQUOTED — assert on ", null," not on '"null"'.
check("active view -> null", ", null," in s_active and "ExportImage(" in s_active, s_active)
check("active view, no Transact", "Transact" not in s_active, s_active)
check("model mode hides annotation (hideAnnotation: true)", ", true)" in s_active, s_active)

s_named = T._export_view_snippet(r"C:\tmp\view_ab12cd34", '3D View - {3D}', 2000, False)
check("named view is quoted", '"3D View - {3D}"' in s_named, s_named)
check("verbatim path keeps backslashes", '@"C:\\tmp\\view_ab12cd34"' in s_named, s_named)
check("pixel size reaches the call", ", 2000," in s_named, s_named)
check("non-model mode keeps annotation (hideAnnotation: false)", ", false)" in s_named, s_named)

s_quote = T._export_view_snippet(r"C:\tmp\v", 'He said "hi"', 1200, True)
check("embedded quote is escaped", '\\"hi\\"' in s_quote, s_quote)

# The "tags" mode is a separate snippet: it keeps dimensions/tags and hides only the
# datum markers, wrapped in a TransactionGroup so the rollback restores the view.
s_tags = T._export_view_tags_snippet(r"C:\tmp\view_ab12cd34", '3D View - {3D}', 1200)
check("tags snippet uses a TransactionGroup", "TransactionGroup" in s_tags, s_tags[:200])
check("tags snippet rolls back (view restored)", "RollBack()" in s_tags, s_tags[:200])

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
# ⚠ RETARGETED 2026-10-27, reason superseded 2026-10-28. This used to assert `pick_object` was
#   present and stop at seven tools. It was first dropped here as "a gallery `Params` concern";
#   the ruling of 2026-10-28 is broader — the tool is retired from EVERY domain (RETIRED.md R11)
#   because an agent cannot signal a pending pick. Asserting its presence asserted the defect.
check("the ten REPL tools are registered",
      all(n in tool_names for n in
          ["ping", "get_context", "export_view", "_explore_revit_data",
           "_execute_dynamic_query", "_search_schema", "_read_extension_methods",
           "list_skills", "read_skill", "get_globals"]),
      f"tools={tool_names}")
check("pick_object is absent from this domain (RETIRED.md R11)",
      "pick_object" not in tool_names, f"tools={tool_names}")
print(f"  tools now: {sorted(tool_names)}")

print("\n== 5. the skill set is the shared methods MINUS modelling ==")
# ⚠⚠ RETARGETED 2026-10-27 (operator ruling): **`paracore-model` is what models.** This server
#   generates REPL on the fly against the raw Revit API, LINQ and the DSL — it does not carry a
#   modelling curriculum. So `create-geometry` is filtered OUT of gen's catalogue, and the check
#   is not "nine are registered" any more; it is "exactly eight, and modelling is not one".
METHOD = ["query-filter", "aggregate-group", "parameter-access", "write-modify",
          "display-visualize", "discovery-debug",
          "identity-orientation", "materials-units"]
SPECIALIST = ["project-modeling", "annotations-dimensions",
              "family-authoring", "massing-forms"]
# ⚠ RETARGETED 2026-10-27: `_SKILL_DESCRIPTIONS` / `_SKILL_CACHE` were module globals of the
#   OLD per-repo mcp_server.py. The registry now lives once in `mcp_core.shared_skills`, and
#   skill text is loaded through `mcp_core.domain.load_skill_text`. Reading the old names was
#   an AttributeError, not a check — the gate had been dead, not failing.
from mcp_core.domain import load_skill_text, skill_catalogue  # noqa: E402
from mcp_core.shared_skills import SHARED_SKILL_DESCRIPTIONS  # noqa: E402

_served = [s.name for s in skill_catalogue(S.DOMAIN)]
check("exactly eight skills are offered", sorted(_served) == sorted(METHOD), f"{_served}")
check("create-geometry is NOT offered (modelling is paracore-model's job)",
      "create-geometry" not in _served, f"{_served}")
check("read_skill('create-geometry') is refused, not served",
      not load_skill_text(S.DOMAIN, "create-geometry"))
for _name in METHOD:
    _body = load_skill_text(S.DOMAIN, _name) or ""
    check(f"{_name} loads (not 'Skill not found')",
          "Skill not found" not in _body and len(_body) > 500, f"{len(_body)} chars")
for _name in SPECIALIST:
    check(f"specialist skill GONE: {_name}", _name not in SHARED_SKILL_DESCRIPTIONS)

print("\n== 6. no served skill or instruction routes to a server this repo does not ship ==")
# ⚠ RETARGETED 2026-10-27 (fifth pre-release review). These checks used to ASSERT a dead
#   pointer ("create-geometry routes a building to paracore-model"). `paracore-model` /
#   `paracore-family` are sibling products, not something a reader of THIS server can call.
#   The pointer is gone; the check is GENERALISED over every served skill rather than
#   inverted on one file — a scan for the class of defect, not the string found this time.
_FOREIGN = ("paracore-model", "paracore-family")
for _name in _served:
    _text = (load_skill_text(S.DOMAIN, _name) or "").lower()
    check(f"{_name} names no foreign server", not any(f in _text for f in _FOREIGN))
dv = load_skill_text(S.DOMAIN, "display-visualize") or ""
check("display-visualize documents export_view", "export_view(" in dv)
check("display-visualize keeps ExportImage", "ExportImage(" in dv)

print("\n== 7. the server instructions carry the generalist identity ==")
instr = S.mcp.instructions or ""
check("instructions say this server is the GENERALIST", "GENERALIST" in instr)
check("instructions allow the raw Revit API / LINQ", "LINQ" in instr)
check("instructions name no foreign server",
      not any(f in instr for f in _FOREIGN))
check("instructions defer to list_skills for scope", "list_skills" in instr)

print(f"\n{'=' * 60}")
print(f"{checks - len(failures)}/{checks} checks passed")
if failures:
    print("FAILURES: " + ", ".join(failures))
    sys.exit(1)
print("ALL CHECKS PASSED")
