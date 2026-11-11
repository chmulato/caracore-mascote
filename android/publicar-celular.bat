@echo off
setlocal EnableDelayedExpansion
REM ============================================================================
REM Instala o APK pdv-sms-enviar no celular via ADB.
REM Antes, valida: ADB, dispositivo unico conectado e autorizado, Android API>=24.
REM Requer: ANDROID_HOME (platform-tools com adb). Veja README-PDV-SMS.md.
REM Se o APK nao existir, executa build.bat.
REM Log: publicar-celular.log na pasta do script.
REM ============================================================================

cd /d "%~dp0"
set "LOG=%~dp0publicar-celular.log"

call :log "=== Inicio (log: %LOG%) ==="

REM --- ANDROID_HOME (igual ao build.bat) ---
if not defined ANDROID_HOME (
    if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
    if not defined ANDROID_HOME (
        call :log "[ERRO] ANDROID_HOME nao definido"
        call :log "Defina ANDROID_HOME. Ex.: set ANDROID_HOME=%%LOCALAPPDATA%%\Android\Sdk"
        call :log "Veja README-PDV-SMS.md. Instale: sdkmanager platform-tools"
        call :log "=== Fim (ERRO) ==="
        exit /b 1
    )
)
if "%ANDROID_HOME:~-1%"=="\" set "ANDROID_HOME=%ANDROID_HOME:~0,-1%"
call :log "ANDROID_HOME=!ANDROID_HOME!"

set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
if not exist "%ADB%" (
    call :log "[ERRO] adb nao encontrado: !ADB!"
    call :log "Instale: sdkmanager platform-tools"
    call :log "Ou: sdkmanager --sdk_root=ANDROID_HOME platform-tools"
    call :log "=== Fim (ERRO) ==="
    exit /b 1
)
call :log "ADB=!ADB!"

REM --- APK: gerar se nao existir (Gradle: build\outputs\apk\debug\) ---
set "APK=build\outputs\apk\debug\pdv-sms-enviar-1.0.apk"
if not exist "!APK!" (
    call :log "[INFO] APK nao encontrado. Executando build.bat..."
    call "%~dp0build.bat"
    if !ERRORLEVEL! neq 0 (
        call :log "[ERRO] build.bat falhou (ERRORLEVEL=!ERRORLEVEL!)"
        call :log "=== Fim (ERRO) ==="
        exit /b 1
    )
    if not exist "!APK!" (
        call :log "[ERRO] Build concluido, mas APK nao foi gerado"
        exit /b 1
    )
)
call :log "APK=!APK!"
set "APK_ABS=%~dp0build\outputs\apk\debug\pdv-sms-enviar-1.0.apk"
if "!APK_ABS!"=="" (
    call :log "[ERRO] APK_ABS vazio. Verifique %%~dp0."
    exit /b 1
)
set "APKSIZE=0"
if exist "!APK_ABS!" for %%A in ("!APK_ABS!") do set "APKSIZE=%%~zA"
if "!APKSIZE!"=="" set "APKSIZE=0"
if !APKSIZE! LEQ 0 (
    call :log "[ERRO] APK vazio ou inexistente. Rode build.bat antes. Tamanho=!APKSIZE! bytes"
    call :log "=== Fim (ERRO) ==="
    exit /b 1
)
call :log "APK tamanho=!APKSIZE! bytes"

REM --- 1. Dispositivo conectado e autorizado (state=device) ---
set "STATE="
"%ADB%" get-state > "%~dp0pdv_adb_state.txt" 2>> "%LOG%"
if exist "%~dp0pdv_adb_state.txt" set /p STATE=<"%~dp0pdv_adb_state.txt"
if exist "%~dp0pdv_adb_state.txt" del "%~dp0pdv_adb_state.txt" 2>nul
call :log "adb get-state -> STATE=!STATE!"

if not "!STATE!"=="device" (
    set "IS_OFFLINE=0"
    set "IS_UNAUTH=0"
    "%ADB%" devices > "%~dp0pdv_adb_devices.txt" 2>&1
    findstr /i "offline" "%~dp0pdv_adb_devices.txt" >nul 2>&1
    if !ERRORLEVEL! equ 0 set "IS_OFFLINE=1"
    findstr /i "unauthorized" "%~dp0pdv_adb_devices.txt" >nul 2>&1
    if !ERRORLEVEL! equ 0 set "IS_UNAUTH=1"

    if "!IS_OFFLINE!"=="1" (
        call :log "Dispositivo em OFFLINE. Tentando adb kill-server + start-server..."
        "%ADB%" kill-server >> "%LOG%" 2>&1
        "%ADB%" start-server >> "%LOG%" 2>&1
        timeout /t 2 /nobreak >nul 2>&1
        "%ADB%" get-state > "%~dp0pdv_adb_state.txt" 2>> "%LOG%"
        if exist "%~dp0pdv_adb_state.txt" set /p STATE=<"%~dp0pdv_adb_state.txt"
        if exist "%~dp0pdv_adb_state.txt" del "%~dp0pdv_adb_state.txt" 2>nul
        call :log "Apos restart do ADB: STATE=!STATE!"
    )

    if not "!STATE!"=="device" if "!IS_UNAUTH!"=="1" (
        call :log "Dispositivo NAO AUTORIZADO. Reiniciando ADB para o aviso 'Permitir depuracao USB?' reaparecer no celular..."
        "%ADB%" kill-server >> "%LOG%" 2>&1
        "%ADB%" start-server >> "%LOG%" 2>&1
        call :log "Aguardando 8 s. Toque em PERMITIR no celular se o aviso aparecer."
        timeout /t 8 /nobreak >nul 2>&1
        "%ADB%" get-state > "%~dp0pdv_adb_state.txt" 2>> "%LOG%"
        if exist "%~dp0pdv_adb_state.txt" set /p STATE=<"%~dp0pdv_adb_state.txt"
        if exist "%~dp0pdv_adb_state.txt" del "%~dp0pdv_adb_state.txt" 2>nul
        call :log "Apos reinicio do ADB: STATE=!STATE!"
    )

    if not "!STATE!"=="device" (
        call :log "[ERRO] Nenhum celular pronto. STATE=!STATE!"
        if "!IS_OFFLINE!"=="1" (
            call :log "Celular em OFFLINE: desligue e reconecte o cabo USB; no celular aceite 'Permitir depuracao USB' e marque 'Sempre permitir'."
            call :log "Se persistir: Opcoes do desenvolvedor -^> Revogar autorizacoes de depuracao USB, depois reconecte e aceite de novo."
            call :log "Tente tambem em outro terminal: adb kill-server e adb start-server"
        ) else if "!IS_UNAUTH!"=="1" (
            call :log "Celular NAO AUTORIZADO: no celular deve aparecer 'Permitir depuracao USB?'. Toque em PERMITIR (e marque 'Sempre permitir' se existir)."
            call :log "Se nao aparecer: desbloqueie a tela, reconecte o cabo ou va em Opcoes do desenvolvedor -^> Revogar autorizacoes de depuracao USB, reconecte e aceite de novo."
        ) else (
            call :log "Conecte um celular por USB com Depuracao USB ativada e autorize o PC."
        )
        "%ADB%" devices
        "%ADB%" devices >> "%LOG%" 2>&1
        del "%~dp0pdv_adb_devices.txt" 2>nul
        call :log "=== Fim (ERRO) ==="
        exit /b 1
    )
    del "%~dp0pdv_adb_devices.txt" 2>nul
)

REM --- 2. Compatibilidade: Android 7.0 (API 24) ou superior ---
set "API="
"%ADB%" shell getprop ro.build.version.sdk > "%~dp0pdv_adb_api.txt" 2>> "%LOG%"
if exist "%~dp0pdv_adb_api.txt" set /p API=<"%~dp0pdv_adb_api.txt"
if exist "%~dp0pdv_adb_api.txt" del "%~dp0pdv_adb_api.txt" 2>nul
if not defined API (
    call :log "[ERRO] Nao foi possivel obter ro.build.version.sdk. API vazio."
    call :log "=== Fim (ERRO) ==="
    exit /b 1
)
set "API=!API: =!"
call :log "API=!API! (min 24)"

if !API! LSS 24 (
    call :log "[ERRO] Android 7.0 (API 24) ou superior necessario. Este aparelho: API !API!"
    call :log "=== Fim (ERRO) ==="
    exit /b 1
)

call :log "[OK] Celular compativel. Instalando..."

REM --- 2.5 Desativar verificador de instalacao ADB (reduz INSTALL_FAILED_VERIFICATION_FAILURE; pode falhar sem root) ---
call :log "Tentando desativar verifier_verify_adb_installs e package_verifier_enable..."
"%ADB%" shell "settings put global verifier_verify_adb_installs 0" >> "%LOG%" 2>&1
"%ADB%" shell "settings put global package_verifier_enable 0" >> "%LOG%" 2>&1

REM --- 3. Instalar ---
set "APK_FULL=%~dp0build\outputs\apk\debug\pdv-sms-enviar-1.0.apk"
call :log "Executando: adb install -r !APK_FULL!"
"%ADB%" install -r "!APK_FULL!" > "%~dp0pdv_adb_install.txt" 2>&1
set "INSTALL_ERR=!ERRORLEVEL!"
type "%~dp0pdv_adb_install.txt"
type "%~dp0pdv_adb_install.txt" >> "%LOG%" 2>nul
if !INSTALL_ERR! neq 0 (
    call :log "adb install -r falhou. Tentando adb install -r -t..."
    "%ADB%" install -r -t "!APK_FULL!" > "%~dp0pdv_adb_install.txt" 2>&1
    set "INSTALL_ERR=!ERRORLEVEL!"
    type "%~dp0pdv_adb_install.txt"
    type "%~dp0pdv_adb_install.txt" >> "%LOG%" 2>nul
)
if !INSTALL_ERR! neq 0 (
    call :log "Tentando push + pm install (evita Streamed Install)..."
    "%ADB%" push "!APK_FULL!" /data/local/tmp/pdv-sms-enviar.apk >> "%LOG%" 2>&1
    if !ERRORLEVEL! neq 0 (
        call :log "[ERRO] adb push tambem falhou."
        del "%~dp0pdv_adb_install.txt" 2>nul
        call :log "=== Fim (ERRO) ==="
        exit /b 1
    )
    "%ADB%" shell pm install -r -t /data/local/tmp/pdv-sms-enviar.apk > "%~dp0pdv_adb_install.txt" 2>&1
    set "INSTALL_ERR=!ERRORLEVEL!"
    "%ADB%" shell rm -f /data/local/tmp/pdv-sms-enviar.apk 2>nul
    type "%~dp0pdv_adb_install.txt"
    type "%~dp0pdv_adb_install.txt" >> "%LOG%" 2>nul
)
del "%~dp0pdv_adb_install.txt" 2>nul
if !INSTALL_ERR! neq 0 (
    call :log "[ERRO] adb install falhou. ERRORLEVEL=!INSTALL_ERR!"
    call :log "Se for INSTALL_FAILED_VERIFICATION_FAILURE:"
    call :log "  1. Tente no celular (pode precisar root): adb shell settings put global verifier_verify_adb_installs 0 e package_verifier_enable 0"
    call :log "  2. Desative Play Protect: Google -^> Seguranca -^> Verificacao de apps"
    call :log "  3. Copie o APK para o celular e instale abrindo o arquivo (ex.: !APK_FULL!)"
    call :log "=== Fim (ERRO) ==="
    exit /b 1
)

call :log "[OK] pdv-sms-enviar instalado. Aceite a permissao SMS na primeira execucao."
call :log "=== Fim (OK) ==="
exit /b 0

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1>> "%LOG%"
goto :eof
