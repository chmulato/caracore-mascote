; Instalador do Gaspar - Mascote Cara Core
; Compile com: python packaging/windows/build_windows.py
; Ou: ISCC.exe /DMyAppVersion=1.7.3 /DMySourceRoot=<raiz do repo> gaspar.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.7.3"
#endif
#ifndef MySourceRoot
  #define MySourceRoot "..\.."
#endif

#define MyAppName "Gaspar - Mascote Cara Core"
#define MyAppPublisher "Cara Core Informatica"
#define MyAppExeName "gaspar.exe"
#define MyBlackBoxExeName "gaspar_blackbox.exe"

[Setup]
AppId={{B7C4E1A2-9F3D-4E58-A1C6-2D7B8E4F0A93}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Cara Core\Gaspar
DefaultGroupName=Cara Core
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#MySourceRoot}\dist\installer
OutputBaseFilename=GasparSetup-{#MyAppVersion}
SetupIconFile={#MySourceRoot}\assets\gaspar.ico
UninstallDisplayIcon={app}\gaspar\gaspar.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
LicenseFile={#MySourceRoot}\LICENSE

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"
Name: "startup"; Description: "Iniciar o Gaspar junto com o Windows"; GroupDescription: "Inicializacao:"; Flags: unchecked

[Files]
Source: "{#MySourceRoot}\dist\windows\gaspar\*"; DestDir: "{app}\gaspar"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MySourceRoot}\dist\windows\gaspar_blackbox\*"; DestDir: "{app}\gaspar_blackbox"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Gaspar"; Filename: "{app}\gaspar\{#MyAppExeName}"; WorkingDir: "{app}\gaspar"; IconFilename: "{app}\gaspar\{#MyAppExeName}"
Name: "{group}\Gaspar BlackBox"; Filename: "{app}\gaspar_blackbox\{#MyBlackBoxExeName}"; WorkingDir: "{app}\gaspar_blackbox"; IconFilename: "{app}\gaspar_blackbox\{#MyBlackBoxExeName}"
Name: "{autodesktop}\Gaspar"; Filename: "{app}\gaspar\{#MyAppExeName}"; WorkingDir: "{app}\gaspar"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "GasparCaraCore"; ValueData: """{app}\gaspar\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startup

[Run]
; A atualizacao silenciosa e reaberta pelo proprio Gaspar, depois que a
; instalacao termina; por isso nao ha entrada de [Run] para o modo silencioso.
Filename: "{app}\gaspar\{#MyAppExeName}"; Description: "Abrir o Gaspar agora"; Flags: nowait postinstall skipifsilent runasoriginaluser
