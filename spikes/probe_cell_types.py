"""What TYPE does a GetNum value arrive as — JSON number or string?

The float-noise fix depends on this: a JSON number can be re-formatted, a string
that already carries the noise cannot (well, it can, but the fix belongs elsewhere).
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import mcp_server  # noqa: E402,F401
from mcp_core import tools as t  # noqa: E402
from grpc_client import execute_repl  # noqa: E402

code = (
    'GetElements("Walls").Select(e => new { Id = e.Id.Value, '
    'H = e.GetNum("Unconnected Height", "m") }).Table()'
)
raw = execute_repl(code, "probe-types", source="mcp_agent")
print("keys:", list(raw.keys()))
structured = raw.get("structuredOutput", raw.get("structured_output"))
print("structured type:", type(structured))
item = structured[0]
print("item keys:", list(item.keys()))
data = item.get("data")
print("data type:", type(data))
if isinstance(data, str):
    print("data[:200]:", data[:200])
    data = json.loads(data)
print("row0:", data[0])
for k, v in data[0].items():
    print(f"  {k!r} -> {type(v).__name__} = {v!r}")
print()
print("summarized:")
print(t.summarize_output(raw) if hasattr(t, "summarize_output") else "n/a")
