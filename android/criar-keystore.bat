@echo off
setlocal
REM ============================================================================
REM Cria o keystore para assinar o APK de release (build.bat release).
REM Usa keytool do JDK (mesmo JAVA_HOME do build.bat).
REM O keytool pede senha e dados do certificado; o keystore fica neste diretorio.
REM Depois: copie keystore.properties.example para keystore.properties e preencha.
REM ============================================================================

cd /d "%~dp0"

if exist "%~dp0config.bat" (call "%~dp0config.bat") else (set "JAVA_HOME=C:\Program Files\Java\jdk1.8.0_202")
if not exist "%JAVA_HOME%\bin\keytool.exe" (
    echo [ERRO] keytool nao encontrado em: %JAVA_HOME%\bin
    echo Copie config.bat.example para config.bat e edite JAVA_HOME.
    exit /b 1
)

set "KEYSTORE=pdv-sms-release.keystore"
if exist "%KEYSTORE%" (
    echo [AVISO] %KEYSTORE% ja existe. Apague se quiser criar outro.
    exit /b 0
)

echo.
echo [INFO] keytool vai pedir senha e dados (nome, org, etc.). Use os mesmos em keystore.properties.
echo.
"%JAVA_HOME%\bin\keytool.exe" -genkey -v -keystore "%KEYSTORE%" -alias pdv-sms -keyalg RSA -keysize 2048 -validity 10000

if %ERRORLEVEL% neq 0 (
    echo [ERRO] keytool falhou.
    exit /b 1
)

echo.
echo [OK] %KEYSTORE% criado. Proximos passos:
echo   1. copy keystore.properties.example keystore.properties
echo   2. Edite keystore.properties com a senha e caminho do keystore
echo   3. build.bat release
echo.
exit /b 0
