; ═══════════════════════════════════════════════════════════════════════════════
; Paracore-Core Installer — the generalist Revit API MCP server
; ═══════════════════════════════════════════════════════════════════════════════
;
; Usage:
;   ISCC -DMCPName=mcp -DMCPTitle="Paracore-Core" -DVersion=4.6.0 paracore-mcp.iss
;
; Output: Paracore-Core-v4.6.0.exe
;
; ⚠⚠ PRODUCT NAME vs EXE NAME — these deliberately differ (user ruling 2026-10-09).
;   The product is Paracore-Core, but the exe stays paracore-mcp.exe, because the exe
;   name IS the `command` path in every MCP client config: renaming it would break
;   every existing install for no user-visible gain. The four naming surfaces are
;   pinned in paracore-ecosystem/MASTER_SYSTEM_SPEC.md ("PRODUCT NAMING") — change
;   them together, never one at a time.
; ═══════════════════════════════════════════════════════════════════════════════

#ifndef MCPName
  #define MCPName "mcp"
#endif
#ifndef MCPTitle
  #define MCPTitle "Paracore-Core"
#endif
#ifndef Version
  #define Version "0.0.0"
#endif

#define ExeName "paracore-" + MCPName
#define OutputBase MCPTitle + "-v" + Version

[Setup]
AppId={{Paracore-F9E8D7C6-B5A4-3210-FEDC-BA9876543210}}
AppName={#MCPTitle}
AppVersion={#Version}
AppPublisher=Paracore
AppPublisherURL=https://paracore.io
AppSupportURL=https://paracore.io/support
VersionInfoVersion={#Version}

OutputBaseFilename={#OutputBase}

Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Per-user install under %APPDATA% — Claude Desktop looks here for MCP servers
DefaultDirName={userappdata}\paracore-data\mcp-servers
DisableDirPage=yes

SetupIconFile="{#IconPath}"
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
; ⚠ The parenthetical says what THIS tool DOES, and it must DIFFER from every other
;   Paracore tool. Never repeat "(Paracore MCP Server)" across tools — that was the
;   2026-10-09 defect: Core and Forge carried an identical, information-free suffix.
UninstallDisplayName={#MCPTitle} (Revit API MCP server)
UninstallDisplayIcon={app}\{#ExeName}.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The MCP executable — built by build-mcp.ps1 via PyInstaller
Source: "dist\{#ExeName}.exe"; DestDir: "{app}"; Flags: ignoreversion

; Reference docs — bundled as MCP resources
Source: "REPL_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "EXTENSION_METHODS.md"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{cmd}"; Parameters: "/c echo {#MCPTitle} v{#Version} installed successfully. && echo Location: {app}"; \
    Flags: nowait skipifsilent runhidden; \
    Description: "Confirm installation"

[UninstallDelete]
Type: files; Name: "{app}\paracore_mcp.log"
