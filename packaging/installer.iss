; Inno Setup 6 script. Compile with: ISCC /DAppVersion=<version> packaging\installer.iss
; Relative paths below are relative to this file.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8AE3DA70-F3C1-4E6E-BC60-6DC8A6238003}
AppName=Print Cost Calculator
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher=KINGdeusX
AppPublisherURL=https://github.com/KINGdeusX/Print-Cost-Calculator
DefaultDirName={autopf}\Print Cost Calculator
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\pcc\assets\icon.ico
UninstallDisplayIcon={app}\PrintCostCalculator.exe
UninstallDisplayName=Print Cost Calculator
OutputDir=out
OutputBaseFilename=PrintCostCalculator-{#AppVersion}-setup
CloseApplications=yes
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\PrintCostCalculator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Print Cost Calculator"; Filename: "{app}\PrintCostCalculator.exe"
Name: "{autodesktop}\Print Cost Calculator"; Filename: "{app}\PrintCostCalculator.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PrintCostCalculator.exe"; Description: "Launch Print Cost Calculator"; Flags: postinstall nowait skipifsilent
