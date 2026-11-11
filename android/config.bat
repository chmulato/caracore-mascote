@echo off
REM JAVA_HOME usado por build.bat, criar-keystore e instalar-gradle-wrapper.
REM AGP 7.4.2 requer JDK 11+. Este script tenta JDK 11+ antes de JDK 8.
REM Para forcar um JDK, defina apenas: set "JAVA_HOME=C:\Program Files\Java\jdk-17"

set "JAVA_HOME="

REM --- Tentar JDK 11+ em ordem de preferencia ---
if exist "C:\Program Files\Java\jdk-17\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-17" & goto :java_done)
if exist "C:\Program Files\Java\jdk-21\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-21" & goto :java_done)
if exist "C:\Program Files\Java\jdk-11\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-11" & goto :java_done)
if exist "C:\Program Files\Java\jdk-22\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-22" & goto :java_done)
if exist "C:\Program Files\Java\jdk-23\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-23" & goto :java_done)

for /d %%d in ("C:\Program Files\Java\jdk-17*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Java\jdk-21*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Java\jdk-11*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)

for /d %%d in ("C:\Program Files\Eclipse Adoptium\jdk-17*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Eclipse Adoptium\jdk-11*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Microsoft\jdk-11*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Amazon Corretto\jdk17*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Amazon Corretto\jdk11*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)

REM Fallback: JDK 8 (AGP 7.4.2 nao suporta; o build vai falhar com "compatible with Java 11")
set "JAVA_HOME=C:\Program Files\Java\jdk1.8.0_202"
if exist "%JAVA_HOME%\bin\java.exe" (
    echo [AVISO] Nenhum JDK 11+ encontrado. Usando JDK 8. AGP 7.4.2 exige JDK 11+ - o build pode falhar.
    echo         Instale ex: Eclipse Adoptium JDK 17 e o config.bat passara a usa-lo.
)
:java_done
