@echo off
setlocal EnableDelayedExpansion
REM ============================================================================
REM Verifica se o app PDV Enviar SMS esta OK no celular: dispositivo conectado,
REM app instalado e permissao SEND_SMS concedida.
REM   verificar-app.bat -> apenas verifica
REM O envio de teste e feito pelo Gaspar, na janela "Celular / SMS".
REM Requer: ANDROID_HOME, celular via USB, depuracao USB, app instalado.
REM ============================================================================

cd /d "%~dp0"

REM --- ANDROID_HOME e ADB (igual publicar-celular) ---
if not defined ANDROID_HOME (
    if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
    if not defined ANDROID_HOME (
        echo [ERRO] ANDROID_HOME nao definido. Defina ou instale o SDK em %%LOCALAPPDATA%%\Android\Sdk
        exit /b 1
    )
)
if "%ANDROID_HOME:~-1%"=="\" set "ANDROID_HOME=%ANDROID_HOME:~0,-1%"
set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
if not exist "%ADB%" (
    echo [ERRO] adb nao encontrado: %ADB%
    exit /b 1
)

echo.
echo === Verificacao: PDV Enviar SMS no celular ===
echo.

REM --- 1. Dispositivo conectado (alguma linha de adb devices termina em "device") ---
"%ADB%" devices 2>nul | findstr /R "device$" >nul 2>&1
if errorlevel 1 (
    echo [FALHA] Dispositivo: celular nao conectado ou nao autorizado.
    echo            Conecte o celular por USB, ative Depuracao USB e aceite "Permitir depuracao USB".
    "%ADB%" devices 2>nul
    echo.
    exit /b 1
)
echo [OK] Dispositivo: conectado e autorizado

REM --- 2. App instalado? ---
set "INST=0"
"%ADB%" shell pm list packages br.com.caracore.pdv.sms 2>nul | findstr /C:"br.com.caracore.pdv.sms" >nul 2>&1
if !ERRORLEVEL! equ 0 set "INST=1"
if "!INST!"=="0" (
    echo [FALHA] App: pdv-sms-enviar NAO instalado. Rode publicar-celular.bat
    echo.
    exit /b 1
)
echo [OK] App: br.com.caracore.pdv.sms instalado

REM --- 3. Permissao SEND_SMS concedida? ---
set "PERM=0"
set "DUMP=%TEMP%\pdv_verificar_dumpsys.txt"
"%ADB%" shell dumpsys package br.com.caracore.pdv.sms 2>nul > "!DUMP!"
findstr "SEND_SMS" "!DUMP!" 2>nul | findstr "granted=true" >nul 2>&1
if !ERRORLEVEL! equ 0 set "PERM=1"
del "!DUMP!" 2>nul
if "!PERM!"=="0" (
    echo [FALHA] Permissao SEND_SMS: negada ou ainda nao concedida.
    echo            Abra o app no celular uma vez e toque em Permitir quando pedir Enviar e receber SMS.
) else (
    echo [OK] Permissao SEND_SMS: concedida
)

echo.

echo === Resumo: verificacao concluida ===
echo    O envio de teste e feito no Gaspar: janela "Celular / SMS" - botao "Enviar teste".
echo.
if "!PERM!"=="0" exit /b 1
exit /b 0
