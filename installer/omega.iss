; Branded per-user Omega installer. MyAppVersion is supplied by the build script.
#ifndef MyAppVersion
  #error MyAppVersion must be supplied by the build script.
#endif

#define MyAppName "Omega Windows Assistant"
#define MyAppPublisher "Anshuman Pattanayak"
#define MyAppDeveloperURL "https://github.com/ItsAnshumanPattanayak"
#define MyAppURL "https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant"
#define MyAppSupportURL "https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/issues"
#define MyAppUpdatesURL "https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant/releases"
#define MyAppExeName "Omega.exe"
#define MyAppCliExeName "OmegaCLI.exe"

[Setup]
AppId={{6D34FE7E-92F0-4B25-B64A-6210D449A0CE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppDeveloperURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppUpdatesURL}
AppCopyright=Copyright (c) 2026 Anshuman Pattanayak
AppComments=A safety-first, local-first Windows desktop assistant.
DefaultDirName={localappdata}\Programs\Omega
DefaultGroupName=Omega Windows Assistant
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=Omega-Windows-Assistant-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayName={#MyAppName}
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
Name: "{group}\Omega Windows Assistant"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; Comment: "Launch Omega Windows Assistant by Anshuman Pattanayak"
Name: "{group}\Omega Diagnostics"; Filename: "{app}\{#MyAppCliExeName}"; Comment: "Open Omega Windows Assistant diagnostics"
Name: "{autodesktop}\Omega Windows Assistant"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; Comment: "Launch Omega Windows Assistant by Anshuman Pattanayak"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--gui"; Description: "Launch Omega Windows Assistant"; Flags: nowait postinstall skipifsilent unchecked

; User data under {localappdata}\Omega is intentionally not removed on uninstall.
