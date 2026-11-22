; Windows setup wizard for Kvm, built by installer/build_windows.ps1:
;   ISCC /DAppName=Kvm /DAppVersion=1.2.3 /DAppURL=https://kvm.pxlvzn.in installer\windows.iss
;
; Unlike the other PXL apps this one installs for the whole PC (it asks for admin once): the Kvm
; service runs as SYSTEM so another computer's keyboard and mouse also work on admin prompts (UAC)
; and on the sign-in and lock screens, and a program that runs as SYSTEM must live where only
; administrators can change it (Program Files). Updates run the newest setup the same way.

#ifndef AppName
  #define AppName "Kvm"
#endif
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppURL
  #define AppURL "https://kvm.pxlvzn.in"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\" + AppName
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#define AppExe AppName + ".exe"

[Setup]
AppId=PXLVZN.{#AppName}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PXLVZN
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoCompany=PXLVZN
VersionInfoDescription={#AppName} Setup
PrivilegesRequired=admin
DefaultDirName={autopf}\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\assets\icon.ico
WizardStyle=modern
WizardSizePercent=100
OutputDir={#OutputDir}
OutputBaseFilename={#AppName}-Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{commonprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Registers and starts the Kvm service, opens the firewall for it and lets it send Ctrl+Alt+Del.
Filename: "{app}\{#AppExe}"; Parameters: "service-install"; StatusMsg: "Starting the Kvm service..."; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\{#AppExe}"; Parameters: "service-remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "{sys}\taskkill.exe"; Parameters: "/f /t /im {#AppExe}"; Flags: runhidden; RunOnceId: "CloseApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{commonappdata}\PXLVZN\Kvm"
Type: filesandordirs; Name: "{commonappdata}\PXLVZN\KvmControl"

[Code]
// Stop the running service (and any open window) before the files are replaced.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\sc.exe'), 'stop Kvm', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(1500);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /t /im {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;
