; Installer di Trip YTD per Windows (Inno Setup 6). Si crea con src\windows\build.ps1,
; che prepara build\windows\Trip YTD (app + Python embeddable) e passa la versione.
#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#define Root AddBackslash(SourcePath) + "..\.."

[Setup]
AppId={{A6AEF776-64B1-4B8E-95EE-328432069A01}
AppName=Trip YTD
AppVersion={#AppVersion}
AppVerName=Trip YTD {#AppVersion}
AppPublisher=maxtrip81
AppPublisherURL=https://github.com/maxtrip81/Trip-YTD
AppSupportURL=https://github.com/maxtrip81/Trip-YTD/issues
AppUpdatesURL=https://github.com/maxtrip81/Trip-YTD/releases
VersionInfoVersion={#AppVersion}
; installazione per l'utente corrente, senza permessi di amministratore
PrivilegesRequired=lowest
DefaultDirName={autopf}\Trip YTD
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Root}\dist
OutputBaseFilename=Trip-YTD-Windows-Setup
SetupIconFile={#Root}\src\icon.ico
UninstallDisplayIcon={app}\app\icon.ico
UninstallDisplayName=Trip YTD
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Root}\build\windows\Trip YTD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Trip YTD"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\trip_ytd.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app\icon.ico"; Comment: "Audio e video da YouTube"
Name: "{autodesktop}\Trip YTD"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\trip_ytd.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app\icon.ico"; Comment: "Audio e video da YouTube"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\app\trip_ytd.py"""; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Trip YTD}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; chiude Trip YTD se è aperto
Filename: "{app}\runtime\python.exe"; Parameters: """{app}\app\trip_ytd.py"" --quit"; Flags: runhidden waituntilterminated; RunOnceId: "ChiudiTripYTD"

[UninstallDelete]
; componenti scaricati (yt-dlp, Deno, ffmpeg), impostazioni e registro; i file scaricati restano
Type: filesandordirs; Name: "{localappdata}\Trip YTD"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { in un aggiornamento chiude prima Trip YTD, se è aperto }
  if FileExists(ExpandConstant('{app}\runtime\python.exe')) then
    Exec(ExpandConstant('{app}\runtime\python.exe'),
         '"' + ExpandConstant('{app}\app\trip_ytd.py') + '" --quit',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
