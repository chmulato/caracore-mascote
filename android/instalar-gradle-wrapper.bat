@echo off
setlocal
REM ============================================================================
REM Instala o gradle-wrapper.jar. Usa Gradle em GRADLE_89 para gerar o wrapper
REM (sem download). Se nao houver, baixa a distribuicao (~130 MB).
REM O projeto usa Gradle 8.9 (Android Gradle Plugin 8.7 exige JDK 17).
REM Para outro caminho: set GRADLE_89=caminho antes de executar.
REM ============================================================================

cd /d "%~dp0"
if exist "%~dp0config.bat" call "%~dp0config.bat"

if exist "gradle\wrapper\gradle-wrapper.jar" (
    echo gradle-wrapper.jar ja existe. Para reinstalar, apague-o antes.
    exit /b 0
)

if not defined GRADLE_89 set "GRADLE_89=D:\dev\caracore-pdv\tools\gradle-8.9"
if exist "%GRADLE_89%\bin\gradle.bat" (
    echo.
    echo [INFO] Usando Gradle em %GRADLE_89%
    echo        gradle wrapper --gradle-version 8.9
    echo.
    "%GRADLE_89%\bin\gradle.bat" wrapper --gradle-version 8.9
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
echo [INFO] Gradle local nao encontrado. Baixando Gradle 8.9 (~130 MB)...
echo.

set "URL=https://services.gradle.org/distributions/gradle-8.9-bin.zip"
set "SUF=%RANDOM%"
set "ZIP=%TEMP%\gradle-8.9-bin-%SUF%.zip"
set "DIR=%TEMP%\gradle-8.9-extract-%SUF%"

REM Evitar conflito com arquivo em uso (antivirus, execucao anterior)
del "%TEMP%\gradle-8.9-bin.zip" 2>nul
rd /s /q "%TEMP%\gradle-8.9-extract" 2>nul

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

if not exist "%DIR%\gradle-8.9\gradle\wrapper\gradle-wrapper.jar" (
    echo [ERRO] gradle-wrapper.jar nao encontrado no zip.
    rd /s /q "%DIR%" 2>nul
    del "%ZIP%" 2>nul
    exit /b 1
)

mkdir "gradle\wrapper" 2>nul
copy /y "%DIR%\gradle-8.9\gradle\wrapper\gradle-wrapper.jar" "gradle\wrapper\gradle-wrapper.jar" >nul
rd /s /q "%DIR%" 2>nul
del "%ZIP%" 2>nul

echo.
echo [OK] gradle-wrapper.jar instalado. Execute build.bat.
echo.
exit /b 0
