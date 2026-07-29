; Per-user Omega installer. MyAppVersion is supplied by scripts/build_installer.ps1.
#ifndef MyAppVersion
  #error MyAppVersion must be supplied by the build script.
#endif

#define MyAppName "Omega"
#define MyAppPublisher "Omega contributors"
#define MyAppURL "https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant"
#define MyAppExeName "Omega.exe"
#define MyAppCliExeName "OmegaCLI.exe"

[Setup]
AppId={{6D34FE7E-92F0-4B25-B64A-6210D449A0CE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\Omega
DefaultGroupName=Omega
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=output
OutputBaseFilename=Omega-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayName=Omega
Uninstallable=yes
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Omega\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Omega"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"
Name: "{group}\Omega Command Line"; Filename: "{app}\{#MyAppCliExeName}"
Name: "{autodesktop}\Omega"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; Description: "Launch Omega"; Flags: nowait postinstall skipifsilent unchecked

; User data under {localappdata}\Omega is intentionally not removed on uninstall.
