@echo off
REM Chama o script Python que baixa dependencias do Android SDK (build-tools 27.0.3, platform-tools, platforms).
REM Uso: baixar-dependencias-android.bat [--sdk-root=...] [--accept-licenses] [--install-cmdline-tools]

python "%~dp0baixar-dependencias-android.py" %*
if errorlevel 1 exit /b 1
