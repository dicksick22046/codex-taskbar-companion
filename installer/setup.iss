#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{F98B6B74-494B-41F8-A164-6BBAE16801A6}
AppName=Codex Taskbar Companion
AppVersion={#AppVersion}
AppPublisher=Codex Taskbar Companion contributors
AppPublisherURL=https://github.com/dicksick22046/codex-taskbar-companion
DefaultDirName={localappdata}\Programs\CodexTaskbarCompanion
DefaultGroupName=Codex Taskbar Companion
OutputDir=..\build
OutputBaseFilename=setup-payload
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
DisableProgramGroupPage=yes
DisableDirPage=auto
UninstallDisplayIcon={app}\CodexTaskbarCompanion.exe
CloseApplications=yes
RestartApplications=no
AppMutex=Local\CodexTaskbarStatus
WizardStyle=modern

[Tasks]
Name: "autostart"; Description: "Start when I sign in to Windows"; Flags: checkedonce

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"; Check: HasPreviousInstall

[Files]
Source: "..\dist\CodexTaskbarCompanion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Codex Taskbar Companion"; Filename: "{app}\CodexTaskbarCompanion.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "CodexTaskbar"; ValueData: """{app}\CodexTaskbarCompanion.exe"""; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "CodexTaskbar"; Flags: deletevalue; Tasks: not autostart

[Run]
Filename: "{app}\CodexTaskbarCompanion.exe"; Description: "Open Codex Taskbar Companion"; Flags: nowait postinstall skipifsilent

Filename: "{app}\CodexTaskbarCompanion.exe"; Flags: nowait; Check: IsUpdate

[Code]
function HasPreviousInstall: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\CodexTaskbarCompanion.exe'));
end;

function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;
