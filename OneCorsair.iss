; Per-user Windows installation; build with Inno Setup 7 ISCC.exe.
#define AppName "OneCorsair"
#define AppVersion "1.1.1"
#define AppUserModelID "OneCorsair.Downloader"

[Setup]
AppId=OneCorsair
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=OneCorsair
AppPublisherURL=https://github.com/dumuzeyn/OneCorsair
AppSupportURL=https://github.com/dumuzeyn/OneCorsair/issues
AppUpdatesURL=https://github.com/dumuzeyn/OneCorsair/releases
DefaultDirName={localappdata}\Programs\OneCorsair
DefaultGroupName=OneCorsair
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=dist
OutputBaseFilename=OneCorsairSetup
SetupIconFile=assets\download_icon.ico
UninstallDisplayIcon={app}\OneCorsair.ico
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=none
ChangesAssociations=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription=OneCorsair Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "dist\OneCorsair.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\download_icon.ico"; DestDir: "{app}"; DestName: "OneCorsair.ico"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\OneCorsair"; Filename: "{app}\OneCorsair.exe"; WorkingDir: "{app}"; IconFilename: "{app}\OneCorsair.ico"; IconIndex: 0; AppUserModelID: "{#AppUserModelID}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\OneCorsair.exe"; ValueType: string; ValueName: ""; ValueData: "{app}\OneCorsair.exe"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\OneCorsair.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\OneCorsair.exe"; Description: "{cm:LaunchProgram,OneCorsair}"; Flags: nowait postinstall skipifsilent
