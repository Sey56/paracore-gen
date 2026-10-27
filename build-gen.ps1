param(
    
    [string]$Version = ""
)

# Read version from VERSION file if not explicitly provided
if (-not $Version) {
    $VersionFile = Join-Path $PSScriptRoot "VERSION"
    if (Test-Path $VersionFile) {
        $Version = (Get-Content $VersionFile).Trim()
    } else {
        Write-Host "ERROR: VERSION file not found and no -Version specified." -ForegroundColor Red
        exit 1
    }
}

# ⚠ ONE name for everything (2026-10-09): repo, build script, exe, installer, display name,
#   MCP handshake and config key are ALL `paracore-gen` / `Paracore-Gen`. There is no
#   product-name-vs-exe-name split any more — that split existed only because the exe was
#   called paracore-mcp.exe and could not be renamed while installs depended on the path.
#   $mcpName drives the PyInstaller --name (⇒ dist\paracore-gen.exe + paracore-gen.spec),
#   the icon path, InternalName and OriginalFilename. Change it and you MUST change
#   paracore-gen.iss, mcp_server.py's FastMCP() and the client's mcp.json to match —
#   the surfaces are pinned in paracore-ecosystem/MASTER_SYSTEM_SPEC.md ("PRODUCT NAMING").
$mcpName = "paracore-gen"
$description = "Paracore-Gen"

# ── Banner ────────────────────────────────────────────────────────────────
Write-Host '=================================' -ForegroundColor Cyan
Write-Host "  Building $description v$Version"
Write-Host '=================================' -ForegroundColor Cyan

$AgentRoot = $PSScriptRoot
$BuildProjectDir = Join-Path $AgentRoot "mcp-build"

# 1. Sync the isolated build environment
Write-Host "Syncing MCP build environment..." -ForegroundColor Yellow
Push-Location $BuildProjectDir
uv sync 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "uv sync failed!" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}
$BuildPython = Join-Path $BuildProjectDir ".venv\Scripts\python.exe"
Pop-Location

# 2. Generate Windows version info file
$vParts = $Version -split '\.'
$vMajor, $vMinor, $vPatch = [int]$vParts[0], [int]$vParts[1], [int]$vParts[2]
$VersionFile = Join-Path $AgentRoot "version-info.txt"
$versionInfo = @"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($vMajor, $vMinor, $vPatch, 0),
    prodvers=($vMajor, $vMinor, $vPatch, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)
  ),
  kids=[
    StringFileInfo([
      StringTable(u'040904B0', [
        StringStruct(u'CompanyName', u'Paracore'),
        StringStruct(u'FileDescription', u'Paracore-Gen MCP server'),
        StringStruct(u'FileVersion', u'$Version'),
        StringStruct(u'InternalName', u'$mcpName'),
        StringStruct(u'LegalCopyright', u'MIT License'),
        StringStruct(u'OriginalFilename', u'$mcpName.exe'),
        StringStruct(u'ProductName', u'Paracore-Gen'),
        StringStruct(u'ProductVersion', u'$Version')
      ])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@
$versionInfo | Set-Content $VersionFile -Encoding UTF8
Write-Host "  Version info: $Version" -ForegroundColor DarkGray

# 3. Build the executable
Write-Host "Compiling mcp_server.py into standalone executable..." -ForegroundColor Yellow
$IconFile = Join-Path $AgentRoot "icons\$mcpName.ico"
Push-Location $AgentRoot
# ── The SHARED MCP CORE — ONE copy, in the ENGINE repo ────────────────────
# ⚠ It used to be `paracore-gen/mcp_core`, COPIED into this repo (and into three others).
#   It now lives ONCE at `paracore/mcp/` and every MCP IMPORTS it — so one fix reaches all
#   five, and there is no copy left to drift. Addressed BY NAME from the repo's parent,
#   never by a hard-coded directory climb.
$SharedCore = $env:PARACORE_MCP_CORE
if (-not $SharedCore) {
    $SharedCore = Join-Path (Split-Path $AgentRoot -Parent) "paracore\mcp"
}
if (-not (Test-Path (Join-Path $SharedCore "mcp_core\__init__.py"))) {
    Write-Host "BUILD GATE FAILED: the shared MCP core is not at '$SharedCore'." -ForegroundColor Red
    Write-Host "  Expected <parent>\paracore\mcp\mcp_core. Set PARACORE_MCP_CORE to override." -ForegroundColor Red
    exit 1
}
Write-Host "  Shared core: $SharedCore" -ForegroundColor DarkGray

# ⚠ The core's SKILLS and PROMPTS are bundled as DATA under `mcp_core/…` — exactly where
#   prompt_assembler and domain.py look for them at runtime. This repo's OWN skills/ and
#   prompts/ go to the bundle ROOT (`skills/`, `prompts/`), which is where
#   `bootstrap.domain_root()` points a Domain.
# ⚠ Added CONDITIONALLY: PyInstaller fails on a missing --add-data source, and paracore-gen
#   (the generalist) has neither its own skills nor its own prompt overrides.
# ⚠⚠ `VERSION;.` IS MANDATORY, and it MUST BE HERE — in the `--add-data` list, NOT in the `.spec`.
#   ⚠⚠ THE `.spec` IS A BUILD OUTPUT, NOT AN INPUT. This script passes `--name` + `--add-data` on
#   the CLI, so PyInstaller REGENERATES `paracore-gen.spec` and OVERWRITES any edit made to it.
#   MEASURED 2026-10-13: a `VERSION` entry added to the spec was silently gone after a build
#   (grep count 0, spec mtime = build time) while the version stayed wrong — the classic
#   "edited the generated artifact instead of the authority" trap.
#   ⚠ WHY IT MATTERS: `mcp_core.server.apply_server_version` reads `<domain.root>/VERSION`
#   (`sys._MEIPASS` when frozen) to set the MCP handshake's `serverInfo.version`. Without the
#   bundle entry the handshake silently reports the mcp SDK's version — "1.27.2", not "2.0.0".
#   (Forge differs: `build-forge.ps1` builds FROM its spec, so there the spec IS the input.)
$DataArgs = @(
    "--add-data", "VERSION;.",
    "--add-data", "REPL_GUIDE.md;.",
    "--add-data", "EXTENSION_METHODS.md;.",
    "--add-data", "$SharedCore\mcp_core\skills;mcp_core/skills",
    "--add-data", "$SharedCore\mcp_core\prompts;mcp_core/prompts"
)
foreach ($dirName in @("skills", "prompts")) {
    if (Test-Path (Join-Path $AgentRoot $dirName)) { $DataArgs += @("--add-data", "$dirName;$dirName") }
}

& $BuildPython -m PyInstaller --onefile --name $mcpName --paths ".;$SharedCore" `
    --version-file $VersionFile `
    --icon $IconFile `
    --exclude-module logfire `
    --hidden-import mcp `
    --hidden-import mcp.server.fastmcp `
    --hidden-import grpc `
    --hidden-import google.protobuf `
    --hidden-import google.protobuf.descriptor_pool `
    --hidden-import google.protobuf.runtime_version `
    --hidden-import google.protobuf.symbol_database `
    --hidden-import google.protobuf.internal.builder `
    --hidden-import mcp_core `
    --copy-metadata fastmcp `
    @DataArgs `
    mcp_server.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}
Pop-Location

# 4. PyInstaller outputs to dist/ directly (we're running from $AgentRoot)
$ExePath = Join-Path $AgentRoot "dist\$mcpName.exe"

# ── 4b. GATE: every prompt the assembler reads at runtime must be IN the exe ──
# prompt_assembler.py loads mcp_core/prompts/*.md at RUNTIME. When that directory
# is absent from the bundle, _read() returns "[Prompt file not found: X]" for every
# section, so `get_section()` / `build_extension_reference()` return pure placeholders while the
# build reports success — the agent then has no API reference and nothing errors.
# A gate must not silently skip (rule 3) and an empty scan must FAIL.
#
# ⚠ Do NOT search the exe's raw bytes: the PKG is compressed, so present text
# returns 0 matches just like absent text. Extract with PyInstaller's own reader.
Write-Host ''
Write-Host 'Verifying bundled prompts...' -ForegroundColor Yellow
$PromptSrc = Join-Path $SharedCore 'mcp_core\prompts'
$Expected = @(Get-ChildItem -Path $PromptSrc -Filter *.md -File -ErrorAction SilentlyContinue)
if ($Expected.Count -eq 0) {
    Write-Host 'BUILD GATE FAILED: no prompt files found in mcp_core/prompts — the' -ForegroundColor Red
    Write-Host 'gate has lost its subject and cannot verify anything.' -ForegroundColor Red
    exit 1
}
$Verify = Join-Path $AgentRoot 'spikes\verify_bundled_prompts.py'
if (Test-Path $Verify) {
    & $BuildPython $Verify $ExePath $PromptSrc
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'BUILD GATE FAILED: prompts are not correctly bundled.' -ForegroundColor Red
        exit 1
    }
} else {
    # ⚠ A gate that silently SKIPS is not a gate (same reason as the skills gate below).
    Write-Host "BUILD GATE FAILED: $Verify is missing; prompt bundling cannot be verified." -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host 'Verifying bundled skills...' -ForegroundColor Yellow
# ⚠⚠ WHY THIS GATE EXISTS (2026-10-27): `read_skill` fails POLITELY. With no skills in
#   the bundle it answers "No skill named 'query-filter'. Available: query-filter,
#   aggregate-group, ..." — a list of the very skills it cannot open. Nothing raises,
#   the build reports success, and a source run is unaffected, so the exe is the only
#   place the fault is visible. Same failure shape as the prompt gate above.
#   Measured on the shipped exe: all 9 present, so this gate PASSES today; it is here
#   so the next --add-data regression cannot ship silently.
$SkillSrc = Join-Path $SharedCore 'mcp_core\skills'
$ExpectedSkills = @(Get-ChildItem -Path $SkillSrc -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') })
if ($ExpectedSkills.Count -eq 0) {
    Write-Host 'BUILD GATE FAILED: no <skill>/SKILL.md found in mcp_core/skills — the' -ForegroundColor Red
    Write-Host 'gate has lost its subject and cannot verify anything.' -ForegroundColor Red
    exit 1
}
$VerifySkills = Join-Path $AgentRoot 'spikes\verify_bundled_skills.py'
if (-not (Test-Path $VerifySkills)) {
    # ⚠ A gate that silently SKIPS is not a gate — this is a hard failure, not a warning.
    Write-Host "BUILD GATE FAILED: $VerifySkills is missing; skill bundling cannot be verified." -ForegroundColor Red
    exit 1
}
& $BuildPython $VerifySkills $ExePath $SkillSrc
if ($LASTEXITCODE -ne 0) {
    Write-Host 'BUILD GATE FAILED: skills are not correctly bundled.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '=================================' -ForegroundColor Green
Write-Host "  $description v$Version — Build Complete"
Write-Host '=================================' -ForegroundColor Green
Write-Host "  Exe: $ExePath"

# ── 5. (Optional) Build Windows installer via Inno Setup ─────────────────
if ($true) {
    $ISCC = $null
    $candidates = @(
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $ISCC = $c; break }
    }

    if (-not $ISCC) {
        Write-Host "ERROR: Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php" -ForegroundColor Red
        exit 1
    }

    Write-Host "Building Windows installer with Inno Setup 6..." -ForegroundColor Yellow
    Write-Host "  Version:  $Version" -ForegroundColor DarkGray

    $InstallersDir = Join-Path $AgentRoot "installers"
    if (!(Test-Path $InstallersDir)) { New-Item -ItemType Directory -Path $InstallersDir | Out-Null }
    $IssFile = Join-Path $AgentRoot "paracore-gen.iss"
    if (-not (Test-Path $IssFile)) {
        Write-Host "ERROR: paracore-gen.iss not found at $IssFile" -ForegroundColor Red
        exit 1
    }
    else {
        # Run ISCC from repo root with relative .iss path (matching free addin pattern)
        # ⚠ /dMCPName is the EXE stem (paracore-<MCPName>); /dMCPTitle is the display name.
        #   They differ only in case, and that is deliberate: `gen` is a filename fragment,
        #   `Paracore-Gen` is the product.
        Push-Location $AgentRoot
        & $ISCC "/dMCPName=gen" "/dMCPTitle=Paracore-Gen" "/dVersion=$Version" "/dIconPath=$IconFile" "/O$InstallersDir" "paracore-gen.iss"
        $issExit = $LASTEXITCODE
        Pop-Location

        if ($issExit -ne 0) {
            Write-Host "Inno Setup build failed!" -ForegroundColor Red
            exit $issExit
        }

        Write-Host "Installer built successfully!" -ForegroundColor Green
    }
}
