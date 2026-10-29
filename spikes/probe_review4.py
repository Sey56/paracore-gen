"""Probe the paracore-gen MCP tool functions DIRECTLY (no MCP protocol, no client).

Run with the build venv:
    mcp-build/.venv/Scripts/python.exe spikes/probe_review4.py <case>

Each case reproduces ONE finding from the Claude Desktop review so the claim is
verified against the code that will actually ship, not against the installed exe.

⚠ Importing mcp_server builds the whole FastMCP server; that is deliberate — the
tool table and the instruction text are part of what is being reviewed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ⚠⚠ BOOT THROUGH THE HARNESS — see spikes/_harness.py. A bare `import mcp_server` gets
#   the tools but NOT the resident dialog watcher, so a probe that provokes a Revit
#   warning leaves Revit parked on a modal dialog that nothing can close.
import _harness  # noqa: E402

t = _harness.boot()
mcp_server = sys.modules["mcp_server"]
from mcp_core.domain import skill_catalogue, load_skill_text  # noqa: E402


def hdr(name):
    print("\n" + "=" * 78)
    print("CASE:", name)
    print("=" * 78)


def case_tools():
    hdr("registered tool list (pick_object must be ABSENT — RETIRED.md R11)")
    names = sorted(mcp_server.mcp._tool_manager._tools.keys())
    for n in names:
        print("  -", n)
    # ⚠ A printed `False` is not a check — nobody diffs it against a remembered expectation.
    #   Say the verdict out loud so this line cannot be read as passing when it is not.
    gone = "pick_object" not in names
    print("\npick_object absent:", "PASS" if gone else "FAIL <-- IT IS BACK")
    print("tool count:", len(names))


def case_skills():
    hdr("skill catalogue + dead cross-product pointers")
    for s in skill_catalogue(mcp_server.DOMAIN):
        print(f"  {s.name:24s} {s.description[:80]}")
    print("\nread_skill('project-modeling') ->")
    print(" ", load_skill_text(mcp_server.DOMAIN, "project-modeling"))


def case_ping():
    hdr("ping")
    print(t.ping())


def case_schema_bad():
    hdr("search_schema('Banana Peels') — must NOT print a usage example")
    out = t.search_schema("Banana Peels")
    print(out)
    print("\n--- assertions ---")
    print("contains 'To query':", "To query" in out)
    print("contains 'No parameters found':", out.startswith("No parameters found"))


def case_schema_ok():
    hdr("search_schema('Walls') — usage example must use .Id.Value")
    out = t.search_schema("Walls")
    tail = out[-400:]
    print(tail)
    print("\n--- assertions ---")
    print("contains IntegerValue:", "IntegerValue" in out)
    print("contains 'Id = e.Id.Value':", "Id = e.Id.Value" in out)


def case_float():
    hdr("float noise in GetNum")
    code = (
        'GetElements("Walls").Select(e => new { Id = e.Id.Value, '
        'H = e.GetNum("Unconnected Height", "m") }).Table()'
    )
    print(t.explore_revit_data(code, "probe float noise"))


def case_context():
    hdr("get_context")
    print(t.get_context_report())


def case_resource():
    hdr("paracore://system-prompt resource registered?")
    res = sorted(mcp_server.mcp._resource_manager._resources.keys())
    for r in res:
        print("  -", r)


CASES = {
    "tools": case_tools,
    "skills": case_skills,
    "ping": case_ping,
    "schema_bad": case_schema_bad,
    "schema_ok": case_schema_ok,
    "float": case_float,
    "context": case_context,
    "resource": case_resource,
}

if __name__ == "__main__":
    want = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in CASES.items():
        if want in ("all", name):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                print(f"!! CASE {name} RAISED: {type(exc).__name__}: {exc}")
