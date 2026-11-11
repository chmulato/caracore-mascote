@echo off
setlocal
REM ============================================================================
REM Recria o keystore (faz backup do antigo). Use se a senha foi esquecida ou
REM o keystore esta corrompido. ATENCAO: app ja publicado na Play Store precisa
REM do MESMO keystore para atualizacao - so recrie se for app NOVO.
REM ============================================================================

cd /d "%~dp0"

set "KEYSTORE=pdv-sms-release.keystore"
if exist "%KEYSTORE%" (
    set "BAK=pdv-sms-release.keystore.bak"
    if exist "%BAK%" del "%BAK%"
    ren "%KEYSTORE%" "%BAK%"
    echo [INFO] Keystore antigo renomeado para %BAK%
    echo.
)
call "%~dp0criar-keystore.bat"
exit /b %ERRORLEVEL%
