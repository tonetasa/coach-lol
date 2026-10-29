@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Criando o instalador do Quiron ===
echo.
echo [1/4] Instalando as ferramentas do Python...
python -m pip install --upgrade pyinstaller -r requirements.txt
if errorlevel 1 goto erro

echo.
echo [2/4] Montando o Quiron.exe (leva 1 a 3 minutos)...
for /f %%v in ('python gerar_info_versao.py') do set "VER=%%v"
if not defined VER goto erro
echo Versao %VER%
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Quiron ^
  --icon icone.ico --version-file version_info.txt --add-data "icone.ico;." ^
  --hidden-import pyttsx3.drivers --hidden-import pyttsx3.drivers.sapi5 ^
  --collect-submodules comtypes --collect-all vosk --collect-all sounddevice ^
  --collect-all customtkinter --hidden-import pystray._win32 ^
  --hidden-import keyring.backends.Windows ^
  --add-data "ui;ui" --hidden-import quiron_web --collect-all webview ^
  --collect-all pythonnet --collect-all clr_loader ^
  coach_app.py
if errorlevel 1 goto erro

echo.
echo [3/4] Procurando o Inno Setup...
set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo Inno Setup nao encontrado. Instalando pelo winget...
  winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC (
  echo.
  echo Nao consegui instalar o Inno Setup automaticamente.
  echo Baixe em https://jrsoftware.org/isdl.php, instale e rode este arquivo de novo.
  goto erro
)

echo.
echo [4/4] Gerando o instalador...
"%ISCC%" /Q /DAppVersion=%VER% Quiron.iss
if errorlevel 1 goto erro

rmdir /S /Q build >nul 2>&1
del /Q Quiron.spec version_info.txt >nul 2>&1

echo.
echo Pronto! O instalador esta em: %~dp0instalador\Quiron-Setup-%VER%.exe
echo Abrindo o instalador...
start "" "%~dp0instalador\Quiron-Setup-%VER%.exe"
echo.
pause
exit /b 0

:erro
echo.
echo Algo deu errado. Tire um print desta janela e mande para o Claude.
echo.
pause
exit /b 1
