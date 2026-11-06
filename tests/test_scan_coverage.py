"""The scan's CLAIMS, as tests — so the README cannot assert coverage the scanner lacks.

WHY THIS EXISTS (2026-11-01). The README said the scan "is the protection" and that the
`FileInfo`/`DirectoryInfo` instance forms were refused. Both were false, and nothing noticed:
a coverage claim written as prose has no failure mode. Measured that day, three snippets walked
straight through —

    new FileInfo(p).Create()            truncated an existing file
    new FileInfo(p).OpenWrite()         opened an existing file for writing
    new FileStream(p, FileMode.Append)  appended to an existing file

— and so did `new Process(); p.Start();`, because every Process rule named the STATIC call.
Those four are pinned below by name.

⚠ A green run means the scanner refuses what this file says it refuses. It does NOT mean the
  scan is a sandbox — see the README's "FILTER, not a sandbox" note. Do not let a passing test
  become the new version of the false claim.

Run standalone (`python tests/test_scan_coverage.py`) or under pytest.
"""

import os as _os
import sys as _sys

# ── the SHARED MCP CORE — walk UP to the sibling checkout, never `..` ────────────
if not getattr(_sys, "frozen", False):
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _dir, _core = _here, None
    for _ in range(8):
        if _os.path.isfile(_os.path.join(_dir, "paracore-mcp-core", "mcp_core", "__init__.py")):
            _core = _os.path.join(_dir, "paracore-mcp-core")
            break
        _up = _os.path.dirname(_dir)
        if _up == _dir:
            break
        _dir = _up
    if _core is None:
        raise RuntimeError(
            "Paracore MCP shared core not found: no `paracore-mcp-core/mcp_core` above "
            f"{_here}. The repos must be SIBLING checkouts under one parent directory."
        )
    if _core not in _sys.path:
        _sys.path.insert(0, _core)

from mcp_core.tool_helpers import (  # noqa: E402
    check_agent_file_policy,
    check_dangerous_patterns,
    check_read_only_violation,
)

README = _os.path.join(_os.path.dirname(_here), "README.md")


def _refused(code):
    """True when EITHER agent guard refuses the snippet."""
    return bool(check_dangerous_patterns(code, agent_only=True)) or bool(
        check_agent_file_policy(code, "agent:mcp")
    )


# ── Every row is a claim the README makes. Keep them in the same order. ─────────
# (label, snippet, must_be_refused)
CLAIMS = [
    # "The network."
    ("HttpClient", 'var c = new HttpClient();', True),
    ("WebClient", 'var c = new WebClient();', True),
    ("raw socket", 'var s = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);', True),
    ("DNS", 'var h = Dns.GetHostName();', True),
    ("System.Net namespace", 'var x = System.Net.IPAddress.Parse("1.2.3.4");', True),

    # "Processes, threads, the registry, native code."
    ("Process.Start", 'Process.Start("cmd");', True),
    ("Process instance  [MEASURED BYPASS]", 'var p = new Process(); p.Start();', True),
    ("Process kill self  [MEASURED BYPASS]", 'Process.GetCurrentProcess().Kill();', True),
    ("new Thread", 'var t = new Thread(() => { });', True),
    ("registry", 'var k = Microsoft.Win32.Registry.CurrentUser;', True),
    ("DllImport", '[DllImport("user32.dll")] static extern int MessageBox(int h);', True),
    ("Marshal", 'var ptr = Marshal.AllocHGlobal(16);', True),

    # "Reflection — the whole family, not a sample of it."
    ("GetTypes", 'var ts = typeof(object).Assembly.GetTypes();', True),
    ("GetMethod", 'var m = typeof(string).GetMethod("Length");', True),
    ("Activator", 'var o = Activator.CreateInstance(typeof(string));', True),
    ("dynamic declaration", 'dynamic d = 1;', True),
    ("Cast<dynamic>  [the documented exemption]", 'var rows = groups.Cast<dynamic>().ToList();', False),

    # "Destroying, moving or replacing a file."
    ("File.WriteAllText", 'File.WriteAllText(p, "x");', True),
    ("File.Copy", 'File.Copy(a, b, true);', True),
    ("FileInfo.Create  [MEASURED BYPASS]", 'new FileInfo(p).Create();', True),
    ("FileInfo.OpenWrite  [MEASURED BYPASS]", 'new FileInfo(p).OpenWrite();', True),
    ("FileMode.Append  [MEASURED BYPASS]", 'new FileStream(p, FileMode.Append);', True),
    ("FileMode.Open", 'new FileStream(p, FileMode.Open);', True),

    # "Creating a NEW file is allowed" — the blessed path must NOT be refused, or the
    # refusal message is teaching something the scanner forbids.
    ("FileMode.CreateNew", 'using (var fs = new FileStream(p, FileMode.CreateNew)) { }', False),
    ("reading a file", 'var text = File.ReadAllText(p);', False),
    ("FileInfo for READING", 'var n = new FileInfo(p).Length;', False),
    ("ordinary LINQ", 'var walls = GetElements<Wall>().Where(w => w.Id != null).ToList();', False),

    # "Sleeping."
    ("Thread.Sleep", 'Thread.Sleep(1000);', True),
]

# ── The read-only path: a different guard, a different claim. ───────────────────
READ_ONLY_CLAIMS = [
    ("SynchronizeWithCentral", 'Doc.SynchronizeWithCentral(o, r);', True),
    ("Export", 'view.Export("x.dwg", o);', True),
    ("ReloadLatest", 'Doc.ReloadLatest(o);', True),
    ("SetVal (Paracore wrapper)", 'el.SetVal("Comments", "x");', True),
    ("SetNum (Paracore wrapper)", 'el.SetNum("Mark", 3);', True),
    ("Hide", 'el.Hide();', True),
    ("Transact (Paracore wrapper)", 'Transact(() => { });', True),
    ("a read", 'var v = el.GetVal("Comments");', False),
    ("a query", 'var walls = GetElements<Wall>();', False),
]


def test_every_documented_refusal_is_refused():
    wrong = []
    for label, code, want in CLAIMS:
        got = _refused(code)
        if got != want:
            wrong.append(f"{label}: expected refused={want}, got {got}")
    assert not wrong, "the scan no longer matches the documented coverage:\n  " + "\n  ".join(wrong)


def test_the_measured_bypasses_stay_closed():
    """The four snippets that walked through on 2026-11-01, pinned by name."""
    bypasses = [
        'new FileInfo(p).Create();',
        'new FileInfo(p).OpenWrite();',
        'new FileStream(p, FileMode.Append);',
        'var p = new Process(); p.StartInfo.FileName = "cmd"; p.Start();',
    ]
    for code in bypasses:
        assert _refused(code), f"REGRESSION — this snippet is not refused again: {code}"


def test_read_only_guard_matches_its_claim():
    wrong = []
    for label, code, want in READ_ONLY_CLAIMS:
        got = bool(check_read_only_violation(code))
        if got != want:
            wrong.append(f"{label}: expected blocked={want}, got {got}")
    assert not wrong, "explore_revit_data no longer matches its claim:\n  " + "\n  ".join(wrong)


def test_readme_does_not_claim_the_scan_is_the_protection():
    """The sentence that was false. If it comes back, this fails."""
    text = open(README, encoding="utf-8").read()
    assert "The scan is the protection" not in text, (
        "README.md claims the scan is the protection again — it is a filter, not a boundary"
    )
    assert "FILTER, not a sandbox" in text, (
        "README.md must say the scan is a filter, not a sandbox"
    )


def test_the_file_policy_claim_is_scoped_to_the_repl_path():
    """MEASURED 2026-11-01: `File.WriteAllText` on a writable path.

    - `execute_repl`   -> refused ("Blocked by the Paracore agent file policy")
    - `execute_script` -> the file was WRITTEN

    That asymmetry is deliberate: an installed gallery tool writes an output CSV at runtime, so
    a blanket file ban on `execute_script` would refuse it. What must NOT happen is the README
    claiming one list covers both paths — that is the same defect class as putting a check on a
    path the agent never takes.
    """
    text = open(README, encoding="utf-8").read()
    assert "REPL entry point's list" in text, (
        "README.md must scope the file/thread list to execute_repl — it is NOT enforced on "
        "execute_script, where a gallery script legitimately writes files"
    )
    # ⚠ RETARGETED 2026-11-06: this anchor used to require the literal `paracore-forge` in
    #   README.md. The public release docs were scrubbed of internal product names, so the
    #   anchor rotted and the test went red on a WORDING change, not a behaviour change.
    #   Retarget, never delete: assert the entry point AND the reason it keeps file access.
    assert "execute_script" in text and "installed tool" in text.lower(), (
        "README.md must name the entry point the list does not cover and say what runs there"
    )
    assert "That is the boundary; this list is the filter" in text, (
        "README.md must name the semantic sandbox as the boundary shared by both paths"
    )


def test_consent_granularity_is_stated_not_implied():
    """OPERATOR DECISION 2026-11-01: consent stays SESSION-level, not per-write.

    The premise of the original review ("session-level is too weak") predates the sandbox. With
    the sandbox holding on both compile paths, per-write prompts buy little and cost a lot: a
    20-step takeoff would show 20 dialogs, and twenty dialogs produce one reflex, not twenty
    judgements. The decision is only defensible while the page also says the dialog is a
    decision and not a defence — so this test pins BOTH halves.
    """
    text = open(README, encoding="utf-8").read()
    assert "once per Revit session, not once per snippet" in text, (
        "README.md must state the consent granularity explicitly — a reader who assumes "
        "per-snippet consent will over-trust it"
    )
    assert "a decision, not a second line of" in text, (
        "README.md must keep saying the dialog is a decision, not a defence"
    )
    assert "sandbox is the thing" in text and "without a human in the loop" in text, (
        "README.md must say what protects the user when nobody reads the dialog"
    )


def test_file_access_is_refused_on_the_repl_channel_only():
    """MEASURED 2026-11-01: file access was a PERSISTENCE primitive, not just a read.

    The old rule was "create only, never replace" — correct about the VERB, silent about the
    LOCATION. `FileMode.CreateNew` worked, and `C:\\ProgramData\\Autodesk\\Revit\\Addins\\2025`
    grants `BUILTIN\\Users:(CI)(WD,AD,WEA,WA)`, so a `.addin` planted there is loaded by Revit at
    the NEXT launch — outside the sandbox, with no consent. Reads were the second half: `C:\\`,
    the profile, the Chrome profile and `Environment.UserName` were all reachable, and whatever
    a snippet reads comes back through tool output to the model provider.

    The fix is a SYMBOL-level refusal of `System.IO` on `execute_repl` only. It is a CHANNEL
    distinction, not a trust level on the `source` string — `execute_script` keeps file access
    because `RoomFinishUpdater` reads a CSV and writes one. This test pins all four halves so a
    later refactor cannot quietly move the check to the path the agent never takes.
    """
    ecosystem = _os.path.dirname(_core)
    engine = _os.path.join(ecosystem, "paracore", "CoreScript.Engine", "Core")

    def read(name):
        with open(_os.path.join(engine, name), encoding="utf-8") as fh:
            return fh.read()

    sandbox = read("ScriptSandbox.cs")
    repl = read("ReplSessionManager.cs")
    compiler = read("ScriptCompiler.cs")

    assert 'private static readonly string[] ReplNamespaces = { "System.IO", "System.Threading" };' in sandbox, (
        "ScriptSandbox must declare System.IO AND System.Threading as channel-scoped refusals — "
        "without System.IO the persistence vector (a .addin in the Addins folder) is open again, "
        "and without System.Threading `Task.Run` escapes the injected budget the way `new Thread` did"
    )
    # TWO compile sites: CSharpScript.Create for the first snippet, ContinueWithAsync for every
    # later one. A check on one of them protects one call per session — the exact bug of
    # 2026-11-01, which is why the count is asserted rather than "at least one".
    #
    # ⚠ COUNT THE CALL ARGUMENT, NOT THE IDENTIFIER (fixed 2026-11-01). The previous version
    #   counted `ReplOnlyNamespaces`, which the channel object replaced — and then counted
    #   COMMENTS as if they were calls. `ReplChannel);` can only appear as the last argument of
    #   a call; prose never ends that way. An anchor that matches a name is an anchor that goes
    #   green on a comment.
    assert repl.count("ScriptSandbox.ReplChannel);") == 2, (
        "ReplSessionManager must pass ScriptSandbox.ReplChannel at BOTH compile sites "
        f"(found {repl.count('ScriptSandbox.ReplChannel);')} call arguments; expected 2)"
    )
    assert "ReplChannel" not in compiler, (
        "ScriptCompiler must NOT pass the REPL channel — execute_script is how a gallery tool "
        "writes its output CSV (RoomFinishUpdater). Refusing there breaks a shipped tool"
    )

    readme = open(README, encoding="utf-8").read()
    assert "A snippet cannot name `System.IO` at all" in readme, (
        "README.md must say System.IO is refused on the REPL channel"
    )
    assert "ScriptApi.Files" in readme and "Files.Root" in readme, (
        "README.md must name the sanctioned file route. Without it a reader concludes file work "
        "is impossible, and the ruling — work is allowed, in one folder — is invisible"
    )
    assert "still has full file access" in readme and "gallery tool" in readme.lower(), (
        "README.md must keep stating that the gallery path retains file access"
    )


def test_the_repl_channel_confines_file_access_to_one_workspace():
    """The operator's ruling (2026-11-01): file WORK stays possible, but only in one folder.

    Refusing `System.IO` outright was correct about the machine and wrong about the job — an
    agent still needs to stage a CSV or read an input. So the ban stays and the engine grows a
    `ScriptApi.Files` façade whose every path is checked at RUNTIME against a workspace root.
    A compile-time rule cannot check a path VALUE: `Path.Combine(root, name)` says nothing about
    `name`, and `..`, a junction or a `\\\\?\\` prefix defeats any static test. That is why this is
    a façade and not "System.IO allowed under a folder" — the second is unenforceable.

    ⚠ This test pins the WIRING and the two constants. The guard itself is proven by
    `_scratch/filesprobe` (19 escape shapes against the shipped `ResolveIn`).
    """
    ecosystem = _os.path.dirname(_core)
    engine = _os.path.join(ecosystem, "paracore", "CoreScript.Engine")

    def read(*parts):
        with open(_os.path.join(engine, *parts), encoding="utf-8") as fh:
            return fh.read()

    files_cs = read("Globals", "ScriptApi.Files.cs")
    repl = read("Core", "ReplSessionManager.cs")
    compiler = read("Core", "ScriptCompiler.cs")
    view_export = read("Globals", "ScriptApi.ViewExport.cs")

    # ── the façade exists and names its own root ─────────────────────────────
    assert 'RootFolderName = "AgentWorkspace"' in files_cs, (
        "ScriptApi.Files must name the workspace folder — it is the one place agent files land"
    )
    assert 'RootOverrideVariable = "PARACORE_AGENT_WORKSPACE"' in files_cs, (
        "the workspace root must be overridable by a documented variable, not hard-coded only"
    )
    # ⚠ Assert the MECHANISMS that are actually there. An earlier draft asserted a literal
    #   `".."` string, which the guard never contains: traversal is handled by canonicalising
    #   with GetFullPath and then testing containment, which is stronger than a substring test.
    for guard in ("GetFullPath", "IsUnder", "ResolveReparsePoints",
                  "alternate data streams", "device paths", "ReservedNames"):
        assert guard in files_cs, f"the path guard must handle {guard}"

    # ── the REPL channel turns confinement ON; the gallery channel does not ──
    assert "ConfineFileAccess = true" in repl, (
        "ReplSessionManager must confine file access — it is the same site that passes "
        "ScriptSandbox.ReplChannel, and the two decisions must not live in different places"
    )
    assert "ConfineFileAccess" not in compiler, (
        "ScriptCompiler (execute_script) must NOT confine — a gallery tool keeps full access "
        "(RoomFinishUpdater reads and writes a CSV)"
    )

    # ── the one file primitive Revit performs itself is guarded too ──────────
    assert "Files.Resolve(path)" in view_export, (
        "ExportImage must route its target through Files.Resolve — Revit writes that file, so "
        "the System.IO ban does not stop it, and it would be the last unconfined write route"
    )

    # ── Python's view-export folder must sit under the SAME root ─────────────
    tools_py = open(_os.path.join(_core, "mcp_core", "tools.py"), encoding="utf-8").read()
    assert "_VIEW_EXPORT_DIR = os.path.join(_VIEW_EXPORT_ROOT, \"views\")" in tools_py, (
        "the MCP's view export must write under the engine's workspace root — an export aimed "
        "at %TEMP% is refused by the engine, so the tool would fail on a call that used to work"
    )
    assert '"Paracore", "AgentWorkspace"' in tools_py, (
        "the Python side must derive the same %LOCALAPPDATA%\\Paracore\\AgentWorkspace root"
    )


# ── Standalone runner: same checks, readable output, no pytest temp dirs. ───────
if __name__ == "__main__":
    checks = [
        test_every_documented_refusal_is_refused,
        test_the_measured_bypasses_stay_closed,
        test_read_only_guard_matches_its_claim,
        test_readme_does_not_claim_the_scan_is_the_protection,
        test_the_file_policy_claim_is_scoped_to_the_repl_path,
        test_consent_granularity_is_stated_not_implied,
        test_file_access_is_refused_on_the_repl_channel_only,
        test_the_repl_channel_confines_file_access_to_one_workspace,
    ]
    failed = 0
    for fn in checks:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}\n      {exc}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    _sys.exit(1 if failed else 0)
