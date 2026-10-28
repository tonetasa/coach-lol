; Instalador do Quíron (Inno Setup 6)
; Usado pelo criar_instalador.bat — a versão vem do versao.py.

#define AppName "Quíron"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppPublisher "Matheus"
#define AppExe "Quiron.exe"

[Setup]
AppId={{0AFCABE1-A057-4110-B1E7-4858EAF3A410}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
; instala só para o seu usuário: não pede senha de administrador
PrivilegesRequired=lowest
DefaultDirName={autopf}\Coach LoL
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=instalador
OutputBaseFilename=Quiron-Setup-{#AppVersion}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=icone.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; fecha o Quíron se ainda estiver aberto (inclusive minimizado na bandeja)
CloseApplications=force
CloseApplicationsFilter=*.exe
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Instalador do {#AppName}
VersionInfoCompany={#AppPublisher}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[InstallDelete]
; restos da versão com o nome antigo (Coach LoL)
Type: files; Name: "{app}\CoachLoL.exe"
Type: files; Name: "{autodesktop}\Coach LoL.lnk"
Type: filesandordirs; Name: "{autoprograms}\Coach LoL"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; remove a entrada "Iniciar com o Windows" (criada pelo app) ao desinstalar
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Quiron"; ValueType: none; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "CoachLoL"; ValueType: none; Flags: deletevalue uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName} agora"; Flags: nowait postinstall skipifsilent
; depois de uma atualização automática (modo silencioso), reabre o app
Filename: "{app}\{#AppExe}"; Flags: nowait skipifnotsilent

[Code]
// Na desinstalação, pergunta se apaga também o histórico de partidas e as configurações
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dados: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dados := ExpandConstant('{userappdata}\Quiron');
    if DirExists(Dados) then
      if MsgBox('Apagar também o histórico de partidas, as configurações e o modelo de voz?' + #13#10 + #13#10 +
                'Pasta: ' + Dados + #13#10 + #13#10 +
                'Escolha "Não" se quiser manter seu histórico para uma reinstalação.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(Dados, True, True, True);
        DelTree(ExpandConstant('{userappdata}\CoachLoL'), True, True, True);
      end;
  end;
end;
