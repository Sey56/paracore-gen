; ═══════════════════════════════════════════════════════════════════════════════
; Paracore-Gen Installer — the generalist Revit API MCP server
; ═══════════════════════════════════════════════════════════════════════════════
;
; Usage (build-gen.ps1 passes these; the defaults below are only a fallback):
;   ISCC -DMCPName=gen -DMCPTitle="Paracore-Gen" -DVersion=4.7.0 paracore-gen.iss
;
; Output: Paracore-Gen-v4.7.0.exe
;
; ⚠⚠ ONE NAME FOR EVERYTHING (2026-10-09). This product used to be called
;   Paracore-MCP, then briefly Paracore-Core, and the exe stayed `paracore-mcp.exe`
;   throughout — so the repo, the exe, the installer and Programs and Features all
;   disagreed. They are now all `paracore-gen` / `Paracore-Gen`: repo, build script,
;   exe, installer, display name, MCP handshake AND the client's config key.
;   The naming surfaces are pinned in paracore-ecosystem/MASTER_SYSTEM_SPEC.md
;   ("PRODUCT NAMING") — change them together, never one at a time.
;
; ⚠ AppId is DELIBERATELY UNCHANGED across the rename. It is the product identity
;   for install/upgrade/uninstall, so keeping it makes this installer UPGRADE the
;   existing entry in place — one row in Programs and Features, renamed — instead of
;   leaving a second, orphaned "Paracore-Core" entry behind. The stale exe is removed
;   by [InstallDelete] below, because Inno does not delete a file it no longer ships.
; ═══════════════════════════════════════════════════════════════════════════════

#ifndef MCPName
  #define MCPName "gen"
#endif
#ifndef MCPTitle
  #define MCPTitle "Paracore-Gen"
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
AppPublisher=Paras Codarch
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
;   2026-10-09 defect: the generalist and Forge carried an identical, information-free
;   suffix, so the two rows were indistinguishable.
UninstallDisplayName={#MCPTitle} (Revit API MCP server)
UninstallDisplayIcon={app}\{#ExeName}.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[InstallDelete]
; ⚠ Runs BEFORE [Files]. Removes the executables this product shipped under its
;   previous names, so an upgrade does not leave a dead paracore-mcp.exe (or the
;   pre-rename log) sitting in the install dir next to the live paracore-gen.exe.
Type: files; Name: "{app}\paracore-mcp.exe"
Type: files; Name: "{app}\paracore_mcp.log"

[Files]
; The MCP executable — built by build-gen.ps1 via PyInstaller
Source: "dist\{#ExeName}.exe"; DestDir: "{app}"; Flags: ignoreversion

; Reference docs — bundled as MCP resources
Source: "REPL_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "EXTENSION_METHODS.md"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{cmd}"; Parameters: "/c echo {#MCPTitle} v{#Version} installed successfully. && echo Location: {app}"; \
    Flags: nowait skipifsilent runhidden; \
    Description: "Confirm installation"

[UninstallDelete]
Type: files; Name: "{app}\paracore_gen.log"
; The pre-rename log name, in case an older install created one and the upgrade
; never ran [InstallDelete] (e.g. a fresh install over a manually-copied exe).
Type: files; Name: "{app}\paracore_mcp.log"
