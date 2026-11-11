# Status atual - PDV Enviar SMS

Documento de acompanhamento do estado da aplicação e da evolução. Atualizado conforme mudanças relevantes.

---

## Propósito

App Android mínimo que envia SMS acionado por intent (ADB ou outro app). É o componente móvel do **Enlace de Contingência** (operação sem internet) do CaraCore-PDV: o PC dispara o envio via `adb shell am start -n br.com.caracore.pdv.sms/.SendSmsActivity -e number "..." -e body "..."`. O celular não precisa de interação após a concessão da permissão SEND_SMS.

---

## Funcionalidades atuais

- Envio de SMS via intent (ADB ou app): `SendSmsActivity` recebe `number` e `body` e envia. Encerra após o envio.
- Painel de controle (launcher): `ConfigActivity` exibe a marca "CaraCore PDV - Envio SMS", texto em linguagem simples (o que o app faz, controle, ajuda), switch para ativar/pausar o envio e exibição de status (Ativo/Pausado). A preferência é armazenada em `SmsPreferences`. Secção "Status da licença": texto em vermelho ("Licença Gratuita / Inativa") ou verde ("Licença Premium Ativa") conforme `isLicencaValida()`. Botão "Verificar Conexão USB" consulta `adb_enabled` e mostra Toast (ativa ou inativa).
- Licença Premium via SMS: `SMSReceiver` escuta `SMS_RECEIVED`, filtra por número oficial (se definido em `SmsPreferences`), extrai chave de "CC-LICENSE:[CHAVE]" ou "CARACORE-KEY:[CHAVE]" e grava em `SmsPreferences`. `isLicencaValida()` valida o formato CC-YYYYMM-{hex8} e exige YYYYMM maior ou igual ao mês atual.
- Exposição para o PDV: `LicencaContentProvider` (authority `br.com.caracore.pdv.sms.licenca`, URI `content://.../licenca`) expõe em `query` as colunas `hardware_id` (ANDROID_ID), `chave`, `valida` (1/0), `mes_ano`. Uso: `adb shell content query --uri content://br.com.caracore.pdv.sms.licenca/licenca`.
- Permissões: SEND_SMS, RECEIVE_SMS, READ_SMS no Manifest; RECEIVE_SMS e READ_SMS solicitadas em runtime (Android 6+) para receber a chave de licença por SMS.
- Tratamento de exceções: `PdvSmsLogger` (tag PdvSms), `ErrorReporter` (Toast e log), `AppExceptionHandler` para exceções não capturadas. Exceções de domínio: `SmsSendException`, `SmsPermissionException`, `SmsDisabledException`, `SmsValidationException`, `PdvSmsException`.
- Ícone: `@android:drawable/sym_def_app_icon`. Label: "CaraCore PDV - Envio SMS" (`strings.xml`).
- Build: Gradle (AGP 7.4.2, Gradle 7.5). Diretório de build em `build\` no projeto; APK em `build\outputs\apk\debug\` ou `release\`; AAB em `build\outputs\bundle\release\pdv-sms-enviar-release.aab`. `config.bat` detecta JDK 11+ (Oracle, Adoptium, Microsoft, Corretto) ou usa JDK 8 com aviso. `gradle.properties` do projeto: `org.gradle.workers.max=1`, `org.gradle.parallel=false`. `build.bat` aceita: (sem args) debug; `release`; `bundle` ou `aab` (AAB para Play Store); `clean`; `clean release`; `clean bundle`. Usa `--max-workers=1`, `-Dorg.gradle.vfs.watch=false`.
- Instalação: `publicar-celular.bat` (adb install). Verificação: `verificar-app.bat` (dispositivo, app, SEND_SMS; opção `test NUMERO`). Assinatura release: `criar-keystore.bat`, `keystore.properties`, `verificar-keystore.bat` (testa senha do keystore), `recriar-keystore.bat` (backup do antigo e cria novo; só para app novo, não para atualização na Play Store).

---

## Pilha técnica

- Android: minSdk 24, targetSdk 27, compileSdk 33.
- Java 8 (source/target). JDK 11+ para o build (AGP 7.4.2).
- Gradle 7.5, Android Gradle Plugin 7.4.2.
- Sem dependências Maven além do AGP. Sem Kotlin.
- Atividades: `ConfigActivity` (MAIN/LAUNCHER), `SendSmsActivity` (exported, excludeFromRecents, taskAffinity vazio). `PdvSmsApp` como Application.
- Componentes: `SMSReceiver` (SMS_RECEIVED, filtro por número oficial, extração CC-LICENSE/CARACORE-KEY), `BackupUpdateReceiver` (intent `br.com.caracore.pdv.sms.BACKUP_UPDATE`), `LicencaContentProvider` (content://br.com.caracore.pdv.sms.licenca/licenca). `SmsPreferences`: chave de licença, número oficial, `isLicencaValida()`.
- Permissões: SEND_SMS, RECEIVE_SMS, READ_SMS.

---

## Build e implantação

- Desenvolvimento: `build.bat` (debug), `build.bat release` (com keystore.properties). `build.bat bundle` ou `build.bat aab` (AAB para Play Store). `build.bat clean` para limpar e evitar AccessDenied em .dex. Combinações: `build.bat clean release`, `build.bat clean bundle`.
- APK debug: `build\outputs\apk\debug\pdv-sms-enviar-1.0.apk`. APK release: `build\outputs\apk\release\pdv-sms-enviar-1.0-release.apk`. AAB: `build\outputs\bundle\release\pdv-sms-enviar-release.aab`.
- Instalação em dispositivo: `publicar-celular.bat`. Requer ANDROID_HOME, adb, dispositivo em state=device, API >= 24.
- Assinatura release e AAB: `criar-keystore.bat` gera `pdv-sms-release.keystore` e alias `pdv-sms`. `keystore.properties` (storeFile, storePassword, keyAlias, keyPassword). `verificar-keystore.bat` valida a senha com keytool -list. `recriar-keystore.bat` renomeia o keystore antigo para .bak e chama `criar-keystore.bat`; usar apenas para app novo, não para atualização na loja.

---

## Limitações conhecidas

- AccessDenied em .dex no Windows: em alguns ambientes (antivírus, IDE) o erro pode ocorrer. Mitigações: `build.bat clean`, exclusão da pasta do projeto em Windows Defender (interface ou `Add-MpPreference -ExclusionPath` em PowerShell como Administrador; basta a pasta do projeto, que inclui `build\`), `excluir-defender-e-build.ps1` (PowerShell como Admin: adiciona exclusão e executa `build.bat clean`), `--max-workers=1`, `org.gradle.workers.max=1`.
- Envio depende de chip/SIM e permissão SEND_SMS. Em modo pausado (ConfigActivity), a lógica de bloqueio é local; o intent ainda chega a `SendSmsActivity` (a checagem de pausa pode ser feita na Activity se for requisito).
- Play Protect pode bloquear instalação via adb (INSTALL_FAILED_VERIFICATION_FAILURE). Contornar: desativar temporariamente ou instalar o APK manualmente.
- Sem ofuscação nem minify no release (minifyEnabled false).

---

## Possível evolução

- Respeitar a preferência de pausa em `SendSmsActivity`: ao receber o intent, checar `SmsPreferences` e, se pausado, não enviar e encerrar com resultado adequado.
- Suporte a `adb shell am start ... --ez dryRun true` (ou extra equivalente) para simular envio em testes.
- Logs opcionais em arquivo (ou via ContentProvider) para diagnóstico em campo.
- Ajuste de targetSdk/compileSdk e de permissões conforme políticas da loja, se houver publicação.
- Opção de ícone próprio em `res` em vez de `sym_def_app_icon`, se for exigência de marca.
- Testes instrumentados (AndroidJUnitRunner) para fluxo de envio e de preferências.

---

## Histórico de alterações (resumo)

- Alinhamento com CaraCore-PDV (v1.1): marca "CaraCore PDV - Envio SMS"; descrição "o que faz" em linguagem de operação sem internet; cores do header em verde (#059669) alinhadas ao portal; README e STATUS referem Enlace de Contingência; strings e comentários em pt-BR.
- Licença Premium: `SMSReceiver` (CC-LICENSE/CARACORE-KEY, filtro por número oficial), `SmsPreferences` (chave, número oficial, `isLicencaValida()`), `LicencaContentProvider` (hardware_id, chave, valida, mes_ano). `ConfigActivity`: status da licença (vermelho/verde), botão "Verificar Conexão USB". Permissões RECEIVE_SMS, READ_SMS no Manifest e em runtime.
- Build em `build\` no projeto; `gradle.properties` e `-Dorg.gradle.vfs.watch=false` para reduzir AccessDenied. Basta uma exclusão no Defender: a pasta do projeto.
- `config.bat`: detecção de JDK 11+ (Java, Adoptium, Microsoft, Corretto) e fallback para JDK 8 com aviso.
- `ConfigActivity` como launcher com painel "CaraCore PDV - Envio SMS"; `SendSmsActivity` para intent de envio; `PdvSmsLogger`, `ErrorReporter`, `AppExceptionHandler`; exceções de domínio; ícone padrão; `SmsPreferences` para ativo/pausado.
- `build.bat`: suporte a `bundle` e `aab` (AAB para Play Store), `clean release`, `clean bundle`; correção de erro "foi inesperado neste momento" no CMD (ajustes em echo e em textos com parênteses dentro de blocos if). AAB renomeado para `pdv-sms-enviar-release.aab` em `build\outputs\bundle\release\`.
- Scripts de keystore: `verificar-keystore.bat` (valida senha com keytool -list); `recriar-keystore.bat` (backup do keystore e criação de novo).
- `BackupUpdateReceiver` no Manifest (intent BACKUP_UPDATE).
- `excluir-defender-e-build.ps1`: adiciona pasta do projeto às exclusões do Defender e executa `build.bat clean`; executar como Administrador.
- Remoção de `android.enableR8` do `gradle.properties` global do Gradle (AGP 7+ tornou a opção obsoleta; R8 é o padrão).
