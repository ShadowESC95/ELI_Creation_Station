; Adapted from ELI_Legal: packaging/windows/eli_legal.iss @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
; ELI Creation Station - Windows installer (Inno Setup 6).
;
; Built by packaging\windows\build.ps1 after PyInstaller has produced build\dist\eli-creation.
; Installs for the current user by default (no administrator rights needed) or for everyone.
; The program and the user's data are kept apart: projects, outputs, models and the provenance ledger live in
; %LOCALAPPDATA%\ELI Creation Station and are never removed by the uninstaller.

#define AppVersion GetEnv("ELI_CREATION_VERSION")
#if AppVersion == ""
  #error Set ELI_CREATION_VERSION (build.ps1 does this)
#endif
#define AppPublisher GetEnv("ELI_CREATION_PUBLISHER")
#if AppPublisher == ""
  #define AppPublisher "ELI Creation Station"
#endif
#define Root "..\.."

[Setup]
; Never change AppId: it is how an upgrade finds the installed copy.
AppId={{690EF32A-860D-444A-88A1-8396D2684EDB}
AppName=ELI Creation Station
AppVersion={#AppVersion}
AppVerName=ELI Creation Station {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ELI Creation Station
DefaultGroupName=ELI Creation Station
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir={#Root}\dist\installers
OutputBaseFilename=ELI_Creation_Station-{#AppVersion}-windows-x64-setup
SetupIconFile=eli_creation.ico
UninstallDisplayIcon={app}\eli-creation-gui.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile={#Root}\packaging\INSTALL_NOTICE.txt
#if FileExists(AddBackslash(SourcePath) + Root + "\LICENSE")
LicenseFile={#Root}\LICENSE
#endif
ChangesEnvironment=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "addtopath"; Description: "Add the eli-creation command to PATH"; GroupDescription: "Command line:"; Flags: unchecked

[Files]
Source: "{#Root}\build\dist\eli-creation\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Root}\packaging\INSTALL_NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ELI Creation Station"; Filename: "{app}\eli-creation-gui.exe"; WorkingDir: "{app}"
Name: "{group}\ELI Creation Station command line"; Filename: "{cmd}"; Parameters: "/K ""{app}\eli-creation.exe"" --help"; WorkingDir: "{app}"
Name: "{group}\Uninstall ELI Creation Station"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ELI Creation Station"; Filename: "{app}\eli-creation-gui.exe"; Tasks: desktopicon

[Registry]
; Per-user PATH entry, only if asked for. Removed again on uninstall.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
; ELI v3, if it is on this machine, opens this copy from its start-up choice and Bundles menu.
Filename: "{app}\eli-creation.exe"; Parameters: "bundle register --if-eli-v3"; Flags: runhidden waituntilterminated
Filename: "{app}\eli-creation-gui.exe"; Description: "Start ELI Creation Station"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; ELI v3's record of this copy goes with it; a record of another copy is left alone.
Filename: "{app}\eli-creation.exe"; Parameters: "bundle unregister --this-copy"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterFromEliV3"

[Messages]
FinishedLabel=ELI Creation Station is installed.%n%nYour projects, outputs, models and the provenance ledger are kept in your user data folder (AppData\Local\ELI Creation Station), separate from the program. Uninstalling never removes them.

[Code]
function NeedsAddPath(Dir: string): Boolean;
var
  Existing: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Existing) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Existing) + ';') = 0;
end;

procedure CurUninstallStepChanged(Step: TUninstallStep);
var
  Existing, Dir: string;
  P: Integer;
begin
  if Step <> usPostUninstall then exit;
  Dir := ExpandConstant('{app}');
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Existing) then
  begin
    P := Pos(';' + Uppercase(Dir), Uppercase(Existing));
    if P > 0 then
    begin
      Delete(Existing, P, Length(Dir) + 1);
      RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Existing);
    end;
  end;
end;
