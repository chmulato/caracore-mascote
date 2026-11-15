@echo off
REM JAVA_HOME usado por build.bat, criar-keystore e instalar-gradle-wrapper.
REM O Android Gradle Plugin 8.7 exige JDK 17 ou superior (nao aceita mais JDK 8/11).
REM Para forcar um JDK, defina apenas: set "JAVA_HOME=C:\Program Files\Java\jdk-17"

set "JAVA_HOME="

REM --- Tentar JDK 17+ em ordem de preferencia ---
if exist "C:\Program Files\Java\jdk-21\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-21" & goto :java_done)
if exist "C:\Program Files\Java\jdk-17\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-17" & goto :java_done)
if exist "C:\Program Files\Java\jdk-22\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-22" & goto :java_done)
if exist "C:\Program Files\Java\jdk-23\bin\java.exe" (set "JAVA_HOME=C:\Program Files\Java\jdk-23" & goto :java_done)

for /d %%d in ("C:\Program Files\Java\jdk-21*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Java\jdk-17*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)

for /d %%d in ("C:\Program Files\Eclipse Adoptium\jdk-17*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)
for /d %%d in ("C:\Program Files\Amazon Corretto\jdk17*") do if exist "%%d\bin\java.exe" (set "JAVA_HOME=%%d" & goto :java_done)

REM Sem JDK 17+: o build falha com "Unsupported class file major version" / AGP exige JDK 17
echo [AVISO] Nenhum JDK 17+ encontrado. O Android Gradle Plugin 8.7 exige JDK 17 - o build vai falhar.
echo         Instale ex: Eclipse Adoptium JDK 17 e o config.bat passara a usa-lo.
:java_done
