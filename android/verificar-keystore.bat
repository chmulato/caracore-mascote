@echo off
setlocal
REM ============================================================================
REM Verifica se a senha do keystore esta correta (para release/bundle).
REM O keytool pede a senha; use a MESMA que esta em keystore.properties.
REM Se listar o alias "pdv-sms", a senha esta certa e o problema pode ser
REM espacos, BOM ou encoding em keystore.properties (salve em ANSI, sem BOM).
REM ============================================================================

cd /d "%~dp0"

if exist "%~dp0config.bat" (call "%~dp0config.bat") else (set "JAVA_HOME=C:\Program Files\Java\jdk-17")
if not exist "%JAVA_HOME%\bin\keytool.exe" (
    echo [ERRO] keytool nao encontrado em: %JAVA_HOME%\bin
    exit /b 1
)

set "KEYSTORE=pdv-sms-release.keystore"
if not exist "%KEYSTORE%" (
    echo [ERRO] %KEYSTORE% nao encontrado. Crie com: criar-keystore.bat
    exit /b 1
)

echo.
echo [INFO] Digite a senha do keystore (a mesma de storePassword/keyPassword em keystore.properties)
echo [INFO] Se aparecer "pdv-sms" abaixo, a senha esta correta.
echo.
"%JAVA_HOME%\bin\keytool.exe" -list -keystore "%KEYSTORE%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [FALHOU] Senha incorreta ou keystore corrompido.
    echo   - Confira storePassword e keyPassword em keystore.properties - geralmente iguais.
    echo   - Sem espacos: storePassword=minhasenha e nao storePassword= minhasenha.
    echo   - Salve keystore.properties em ANSI ou UTF-8 sem BOM.
    echo   - Se esqueceu a senha ou o keystore esta corrompido: apague pdv-sms-release.keystore
    echo     e execute criar-keystore.bat para criar um novo. Atencao: app ja na Play Store
    echo     precisa do mesmo keystore para atualizacao - so recrie se for app novo.
    exit /b 1
)
echo.
echo [OK] Senha valida. Se o build ainda falhar, verifique espacos/encoding em keystore.properties.
exit /b 0
