@echo off
setlocal
REM ============================================================================
REM Instala o gradle-wrapper.jar. Usa Gradle em D:\dev\caracore-pdv\tools\gradle-7.5
REM para gerar o wrapper (sem download). Se nao houver, baixa a distribuicao (~100 MB).
REM Para outro caminho: set GRADLE_7_5=caminho antes de executar.
REM ============================================================================

cd /d "%~dp0"
if exist "%~dp0config.bat" call "%~dp0config.bat"

if exist "gradle\wrapper\gradle-wrapper.jar" (
    echo gradle-wrapper.jar ja existe. Para reinstalar, apague-o antes.
    exit /b 0
)

if not defined GRADLE_7_5 set "GRADLE_7_5=D:\dev\caracore-pdv\tools\gradle-7.5"
if exist "%GRADLE_7_5%\bin\gradle.bat" (
    echo.
    echo [INFO] Usando Gradle em %GRADLE_7_5%
    echo        gradle wrapper --gradle-version 7.5
    echo.
    "%GRADLE_7_5%\bin\gradle.bat" wrapper --gradle-version 7.5
    if %ERRORLEVEL% neq 0 (
        echo [ERRO] gradle wrapper falhou.
        exit /b 1
    )
    if not exist "gradle\wrapper\gradle-wrapper.jar" (
        echo [ERRO] gradle nao gerou gradle-wrapper.jar
        exit /b 1
    )
    echo.
    echo [OK] gradle-wrapper.jar instalado. Execute build.bat.
    echo.
    exit /b 0
)

echo.
echo [INFO] Gradle local nao encontrado. Baixando Gradle 7.5 (~100 MB)...
echo.

set "URL=https://services.gradle.org/distributions/gradle-7.5-bin.zip"
set "SUF=%RANDOM%"
set "ZIP=%TEMP%\gradle-7.5-bin-%SUF%.zip"
set "DIR=%TEMP%\gradle-7.5-extract-%SUF%"

REM Evitar conflito com arquivo em uso (antivirus, execucao anterior)
del "%TEMP%\gradle-7.5-bin.zip" 2>nul
rd /s /q "%TEMP%\gradle-7.5-extract" 2>nul

powershell -NoProfile -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing }"
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Download falhou. Verifique a conexao.
    exit /b 1
)

if not exist "%ZIP%" (
    echo [ERRO] Arquivo zip nao encontrado apos download.
    exit /b 1
)

mkdir "%DIR%" 2>nul
powershell -NoProfile -Command "Start-Sleep -Seconds 1; Expand-Archive -Path '%ZIP%' -DestinationPath '%DIR%' -Force"
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Falha ao extrair. Se o zip estiver em uso, tente de novo em alguns segundos.
    rd /s /q "%DIR%" 2>nul
    del "%ZIP%" 2>nul
    exit /b 1
)

if not exist "%DIR%\gradle-7.5\gradle\wrapper\gradle-wrapper.jar" (
    echo [ERRO] gradle-wrapper.jar nao encontrado no zip.
    rd /s /q "%DIR%" 2>nul
    del "%ZIP%" 2>nul
    exit /b 1
)

mkdir "gradle\wrapper" 2>nul
copy /y "%DIR%\gradle-7.5\gradle\wrapper\gradle-wrapper.jar" "gradle\wrapper\gradle-wrapper.jar" >nul
rd /s /q "%DIR%" 2>nul
del "%ZIP%" 2>nul

echo.
echo [OK] gradle-wrapper.jar instalado. Execute build.bat.
echo.
exit /b 0
