"""
Probe: Append(pipeline) CS0411 rewriter bug — diagnostic edition.

Tests exactly what SemanticTrackingGuard decides for sb.Append(...)
to determine whether the skip set is computed correctly but the
rewriter isn't matching, or whether the guard itself fails.
"""
import sys, subprocess, json, re

GEN = r"C:\Users\seyou\Paracore\paracore-gen\paracore_gen.exe"

# The minimal failing script: StringBuilder.Append collides with LINQ Append
SCRIPT = '''var sb = new StringBuilder();
sb.Append(GetElements("Walls").Count());
Println(sb.ToString());'''

# Build the execute_dynamic_query call
payload = {
    "method": "tools/call",
    "params": {
        "name": "execute_repl",
        "arguments": {"code": SCRIPT}
    }
}

print("=" * 70)
print("PROBE: Append(pipeline) CS0411 diagnostic")
print("=" * 70)
print(f"Script:\n{SCRIPT}")
print("-" * 70)

# Call paracore-gen
import subprocess
result = subprocess.run(
    [GEN],
    input=json.dumps(payload),
    capture_output=True, text=True, timeout=120
)

stdout = result.stdout
stderr = result.stderr

# Try to parse the JSON response
try:
    resp = json.loads(stdout)
    content = ""
    if "result" in resp:
        for item in resp["result"].get("content", []):
            if item.get("type") == "text":
                content += item["text"]
    elif "error" in resp:
        content = json.dumps(resp["error"], indent=2)
    else:
        content = json.dumps(resp, indent=2)[:3000]
except:
    content = stdout[:3000]

print("RESPONSE:")
print(content[:3000])
print("-" * 70)
if stderr:
    print("STDERR (first 2000):")
    print(stderr[:2000])

# Check for CS0411
if "CS0411" in content:
    print("\n>>> BUG REPRODUCED: CS0411 TrackEnumerable<T> on sb.Append")
elif "TrackEnumerable" in content:
    print("\n>>> BUG REPRODUCED: TrackEnumerable wrapping on sb.Append")
elif sb_str := re.search(r'StringBuilder', content):
    print("\n>>> sb.Append compiled — no CS0411")
else:
    print("\n>>> Unexpected output — check manually")
