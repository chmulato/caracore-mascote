@echo off
setlocal
REM ============================================================================
REM Build do APK/AAB com Gradle (Android Gradle Plugin).
REM   build.bat         -> APK debug (teste, publicar-celular)
REM   build.bat release -> APK release assinado (distribuicao, lojas)
REM   build.bat bundle  -> AAB release (Play Store – formato preferido)
REM   build.bat clean   -> limpa build/ (evita AccessDenied em .dex)
REM   build.bat clean release  -> clean + APK release
REM   build.bat clean bundle   -> clean + AAB
REM   Requer keystore.properties (storeFile, storePassword, keyAlias, keyPassword) para release/bundle.
REM Requer: JDK 11+, Android SDK (ANDROID_HOME ou %LOCALAPPDATA%\Android\Sdk).
REM Veja README-PDV-SMS.md para instalar as dependencias.
REM ============================================================================

cd /d "%~dp0"

REM --- Configurar Java 8: config.bat ou padrao ---
if exist "%~dp0config.bat" (call "%~dp0config.bat") else (set "JAVA_HOME=C:\Program Files\Java\jdk1.8.0_202")
if not exist "%JAVA_HOME%\bin\java.exe" (
    echo [ERRO] Java nao encontrado em: %JAVA_HOME%
    echo AGP 7.4.2 requer JDK 11+. Instale ex: Eclipse Adoptium JDK 11 ou 17 e edite config.bat.
    exit /b 1
)
set "PATH=%JAVA_HOME%\bin;%PATH%"
echo [INFO] Java: %JAVA_HOME%

if not defined ANDROID_HOME (
    if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
    if not defined ANDROID_HOME (
        echo [ERRO] ANDROID_HOME nao definido.
        echo Defina apontando para o Android SDK (ex: C:\Users\...\AppData\Local\Android\Sdk^)
        echo ou instale em %LOCALAPPDATA%\Android\Sdk. Veja README-PDV-SMS.md
        exit /b 1
    )
)
if "%ANDROID_HOME:~-1%"=="\" set "ANDROID_HOME=%ANDROID_HOME:~0,-1%"

where java >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Java nao esta no PATH. Veja README-PDV-SMS.md
    exit /b 1
)

if not exist "gradle\wrapper\gradle-wrapper.jar" (
    echo [INFO] gradle-wrapper.jar nao encontrado. Executando instalar-gradle-wrapper.bat...
    call "%~dp0instalar-gradle-wrapper.bat"
    if %ERRORLEVEL% neq 0 (
        echo [ERRO] Falha ao instalar gradle-wrapper. Verifique a conexao.
        echo Alternativa: gradle wrapper --gradle-version 7.5
        exit /b 1
    )
    if not exist "gradle\wrapper\gradle-wrapper.jar" (
        echo [ERRO] gradle-wrapper.jar ainda nao encontrado apos instalacao.
        exit /b 1
    )
    echo/
)

set "DO_CLEAN=0"
if /i "%~1"=="clean" set "DO_CLEAN=1"
if /i "%~2"=="clean" set "DO_CLEAN=1"
set "MODE=debug"
set "BUILD_DIR=build"
set "APK_VERSION="
for /f "tokens=2 delims='" %%V in ('findstr /c:"versionName" build.gradle') do if not defined APK_VERSION set "APK_VERSION=%%V"
if not defined APK_VERSION (
    echo [ERRO] versionName nao encontrado em build.gradle
    exit /b 1
)
set "APK=%BUILD_DIR%\outputs\apk\debug\pdv-sms-enviar-%APK_VERSION%.apk"
if /i "%~1"=="release" set "MODE=release" & set "APK=%BUILD_DIR%\outputs\apk\release\pdv-sms-enviar-%APK_VERSION%-release.apk"
if /i "%~2"=="release" set "MODE=release" & set "APK=%BUILD_DIR%\outputs\apk\release\pdv-sms-enviar-%APK_VERSION%-release.apk"
if /i "%~1"=="bundle" set "MODE=bundle" & set "APK=%BUILD_DIR%\outputs\bundle\release\pdv-sms-enviar-release.aab"
if /i "%~2"=="bundle" set "MODE=bundle" & set "APK=%BUILD_DIR%\outputs\bundle\release\pdv-sms-enviar-release.aab"
if /i "%~1"=="aab" set "MODE=bundle" & set "APK=%BUILD_DIR%\outputs\bundle\release\pdv-sms-enviar-release.aab"
if /i "%~2"=="aab" set "MODE=bundle" & set "APK=%BUILD_DIR%\outputs\bundle\release\pdv-sms-enviar-release.aab"

echo.
echo [BUILD] Modo: %MODE% ^| Clean: %DO_CLEAN% ^| Build: %BUILD_DIR%
echo [BUILD] ANDROID_HOME=%ANDROID_HOME%
echo.

REM Encerra daemons Gradle para liberar locks em build/ (evita AccessDenied em .dex)
echo [BUILD] Etapa: Encerrando daemons Gradle...
call .\gradlew.bat --stop
timeout /t 2 /nobreak 1>nul 2>nul
echo/
if "%DO_CLEAN%"=="1" (
    echo [BUILD] Etapa: Limpando build anterior - clean
    call .\gradlew.bat clean --console=plain --no-daemon
    if exist "build" rmdir /s /q "build" 2>nul
    timeout /t 2 /nobreak 1>nul 2>nul
    echo/
)

REM Se project_dex_archive existe (falha anterior), clean total + pausa para o Windows libertar locks
if exist "build\intermediates\project_dex_archive" (
    echo [BUILD] project_dex_archive encontrado - limpando e aguardando 2s...
    call .\gradlew.bat clean --console=plain --no-daemon
    if exist "build" rmdir /s /q "build" 2>nul
    timeout /t 2 /nobreak 1>nul 2>nul
    echo/
)
if exist "build\intermediates\project_dex_archive" (
    rmdir /s /q "build\intermediates\project_dex_archive" 2>nul
    timeout /t 2 /nobreak 1>nul 2>nul
)

if "%MODE%"=="release" (
    echo [BUILD] Etapa: Compilando APK release - assembleRelease
    call .\gradlew.bat assembleRelease --no-build-cache --console=plain --no-daemon --max-workers=1 -Dorg.gradle.vfs.watch=false
) else (
    if "%MODE%"=="bundle" (
        echo [BUILD] Etapa: Compilando AAB - bundleRelease
        call .\gradlew.bat bundleRelease --no-build-cache --console=plain --no-daemon --max-workers=1 -Dorg.gradle.vfs.watch=false
    ) else (
        echo [BUILD] Etapa: Compilando APK debug - assembleDebug
        call .\gradlew.bat assembleDebug --no-build-cache --console=plain --no-daemon --max-workers=1 -Dorg.gradle.vfs.watch=false
    )
)

if errorlevel 1 (
    echo/
    echo [ERRO] Build falhou. Verifique:
    echo   - ANDROID_HOME e platforms/build-tools - sdkmanager
    echo   - JDK 11+ - AGP 7.4.2 exige Java 11. config.bat prioriza JDK 11+; instale Eclipse Adoptium JDK 17 se necessario.
    echo   - Erro "compatible with Java 11" ou "Java 8": use JDK 11+ em config.bat.
    if "%MODE%"=="release" echo   - keystore.properties com storeFile, storePassword, keyAlias, keyPassword
    if "%MODE%"=="bundle" echo   - keystore.properties com storeFile, storePassword, keyAlias, keyPassword
    echo   - AccessDenied em SendSmsActivity.dex: Execute como Admin: .\excluir-defender-e-build.ps1
    echo     Ou adicione manualmente a pasta do projeto em Exclusoes do Defender: %CD%
    if exist "%APK%" del "%APK%" 2>nul
    exit /b 1
)

REM APK ja em build\outputs\apk\debug\ ou release\ (publicar-celular e outros usam build\outputs\apk\)

echo/
REM --- Validar que o APK/AAB nao esta vazio e tem tamanho minimo ---
set "APKSZ=0"
if exist "%APK%" for %%A in ("%APK%") do set "APKSZ=%%~zA"
if "%APKSZ%"=="" set "APKSZ=0"
set "APKSZ=%APKSZ:,=%"
if %APKSZ% LEQ 0 (
    echo/
    echo [ERRO] APK/AAB nao foi gerado ou esta vazio. Verifique ANDROID_HOME e o log acima.
    if exist "%APK%" del "%APK%" 2>nul
    exit /b 1
)
if %APKSZ% LSS 5000 (
    echo/
    echo [ERRO] Arquivo muito pequeno: %APKSZ% bytes. Pode estar corrompido. Tente: gradlew clean assembleDebug --no-build-cache
    exit /b 1
)

echo/
echo [OK] Saida: %APK% - %APKSZ% bytes
echo/
exit /b 0
