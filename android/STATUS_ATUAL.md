# Status atual - PDV Enviar SMS

Documento de acompanhamento do estado da aplicação e da evolução. Atualizado conforme mudanças relevantes.

---

## Propósito

Celular de envio do PDV pela ponte local do Gaspar. O app escuta a rede Wi-Fi
(`GatewayListenerService`), recebe o pedido **cifrado de ponta a ponta**, abre
com a chave privada que só ele tem, dispara o SMS pelo chip e devolve o
comprovante ao Gaspar. O acionamento por intent/ADB foi encerrado: a activity de
envio não é exportada e exige permissão interna de assinatura.

---

## Funcionalidades atuais

- **Pareamento por QR**: `ScanSetupActivity` lê o código do Gaspar, aplica IP,
  porta, segredo e licença, cria o par de chaves EC P-256 e manda o diagnóstico
  com a chave pública (`SetupDiagnosticHelper`).
- **Envelope de ponta a ponta**: `E2ECrypto` (ECDH P-256, HKDF-SHA256,
  AES-256-GCM, chave privada protegida pelo Android Keystore) e `E2EKeySender`
  (publica a chave em `POST /api/mobile/key` quando o celular já está pareado).
- **Envio**: `GatewayListenerService` (UDP 49999 para descoberta, TCP 49998 para
  comando) decifra o envelope, valida número/mensagem, respeita o switch do app,
  o limite diário de 300 SMS, o `id` repetido e a sequência, e chama o
  `SmsManager`.
- **Comprovante**: `SmsStatusReceiver` devolve "aceito" e "entregue" e
  `SmsReceiptSender` envia ao Gaspar cifrado com o segredo do pareamento.
- Painel de controle (launcher): `ConfigActivity` exibe a marca "CaraCore PDV -
  Envio SMS", texto em linguagem simples, switch para ativar/pausar o envio,
  status da licença (vermelho/verde), botão "Verificar Conexão USB" e o campo
  "Número que envia a licença" (número oficial do SMS de ativação).
- Licença Premium via SMS: `SMSReceiver` escuta `SMS_RECEIVED` e usa a regra de
  `LicenseSms`: exige o número oficial salvo no painel (sem ele, ignora o SMS),
  remetente que confere e chave no formato CC-YYYYMM-{hex8}; grava em
  `SmsPreferences`; `isLicencaValida()` exige mês atual ou futuro.
- Exposição para o PDV: `LicencaContentProvider` (authority
  `br.com.caracore.pdv.sms.licenca`) com `hardware_id` (ANDROID_ID), `chave`,
  `valida` e `mes_ano`. No 1.5 ele está protegido por
  `readPermission` de assinatura (`SMS_INTERNAL`) — só app assinado com a mesma
  chave lê, e o `adb shell content query` deixa de responder. É o que está no
  **1.5 publicado**; o APK do 1.4, também publicado, está exportado e sem
  permissão de leitura. O PDV 4.1.0 não consulta o provedor; o plano dele vem
  de `LicencaPro`.
- **Sem acionamento externo**: `SendSmsActivity` é interna (`exported=false` +
  permissão de assinatura) e o serviço de rede não é exportado.
- Permissões: SEND_SMS e RECEIVE_SMS; o app usa SEND_SMS para enviar e
  RECEIVE_SMS para a licença, e não consulta a caixa de entrada (READ_SMS
  removida em 12/11/2026).
- Tratamento de exceções: `PdvSmsLogger` (tag PdvSms), `ErrorReporter`,
  `AppExceptionHandler`; exceções de domínio em `SmsSendException`,
  `SmsPermissionException`, `SmsDisabledException`, `SmsValidationException` e
  `PdvSmsException`.
- Ícone: `@android:drawable/sym_def_app_icon`. Label: "CaraCore PDV - Envio SMS".
- Build: Gradle (AGP 7.4.2, Gradle 7.5), saída em `build\`; `config.bat` detecta
  JDK 11+; `build.bat` aceita debug, `release`, `bundle`/`aab`, `clean`.
- Instalação: `publicar-celular.bat`. Verificação: `verificar-app.bat`
  (dispositivo, app e SEND_SMS; o teste de envio é feito no Gaspar). Assinatura:
  `criar-keystore.bat`, `verificar-keystore.bat`, `recriar-keystore.bat`.

---

## Pilha técnica

- Android: minSdk 24, targetSdk 27, compileSdk 33.
- Java 8 (source/target). JDK 11+ para o build (AGP 7.4.2).
- Gradle 7.5, Android Gradle Plugin 7.4.2.
- Sem dependências Maven além do AGP. Sem Kotlin.
- Atividades: `ConfigActivity` (MAIN/LAUNCHER), `ScanSetupActivity` (QR),
  `SendSmsActivity` (interna, não exportada). `PdvSmsApp` como Application.
- Componentes: `GatewayListenerService` (UDP 49999 + TCP 49998), `SMSReceiver`
  (licença), `SmsStatusReceiver` (aceito/entregue), `BootReceiver`,
  `BackupUpdateReceiver`, `LicencaContentProvider`.
- Criptografia: `GatewayCrypto` (canal AES-GCM com o segredo do pareamento) e
  `E2ECrypto` (envelope por pedido). Chaves em `SmsPreferences`, com a privada
  embrulhada por chave do Android Keystore.
- Permissões: SEND_SMS, RECEIVE_SMS, INTERNET, CAMERA,
  FOREGROUND_SERVICE, RECEIVE_BOOT_COMPLETED,
  REQUEST_IGNORE_BATTERY_OPTIMIZATIONS.

---

## Build e implantação

- Desenvolvimento: `build.bat` (debug), `build.bat release` (com keystore.properties). `build.bat bundle` ou `build.bat aab` (AAB para Play Store). `build.bat clean` para limpar e evitar AccessDenied em .dex. Combinações: `build.bat clean release`, `build.bat clean bundle`.
- APK debug: `build\outputs\apk\debug\pdv-sms-enviar-1.5.apk`. APK release: `build\outputs\apk\release\pdv-sms-enviar-1.5-release.apk`. AAB: `build\outputs\bundle\release\pdv-sms-enviar-release.aab`.
- Instalação em dispositivo: `publicar-celular.bat`. Requer ANDROID_HOME, adb, dispositivo em state=device, API >= 24.
- Assinatura release e AAB: `criar-keystore.bat` gera `pdv-sms-release.keystore` e alias `pdv-sms`. `keystore.properties` (storeFile, storePassword, keyAlias, keyPassword). `verificar-keystore.bat` valida a senha com keytool -list. `recriar-keystore.bat` renomeia o keystore antigo para .bak e chama `criar-keystore.bat`; usar apenas para app novo, não para atualização na loja.

---

## Limitações conhecidas

- AccessDenied em .dex no Windows: em alguns ambientes (antivírus, IDE) o erro pode ocorrer. Mitigações: `build.bat clean`, exclusão da pasta do projeto em Windows Defender (interface ou `Add-MpPreference -ExclusionPath` em PowerShell como Administrador; basta a pasta do projeto, que inclui `build\`), `excluir-defender-e-build.ps1` (PowerShell como Admin: adiciona exclusão e executa `build.bat clean`), `--max-workers=1`, `org.gradle.workers.max=1`.
- Envio depende de chip/SIM e permissão SEND_SMS. O switch **App ativo** é
  checado no serviço de rede; pedido com o app pausado é recusado com aviso.
- Sem o Gaspar pareado e com chave registrada, o celular não recebe pedido: o
  Gaspar recusa enfileirar (`e2e_required`).
- Play Protect pode bloquear instalação via adb (INSTALL_FAILED_VERIFICATION_FAILURE). Contornar: desativar temporariamente ou instalar o APK manualmente.
- Sem ofuscação nem minify no release (minifyEnabled false).
- `allowBackup` está ligado: as preferências podem ir para o backup do Google. A
  chave privada do envelope fica presa ao Keystore e não funciona em outro
  aparelho; o segredo do pareamento deve ser trocado pareando de novo.

---

## Possível evolução

- Desligar `allowBackup` ou excluir as preferências da ponte do backup.
- Logs opcionais em arquivo (sem número nem texto) para diagnóstico em campo.
- Ajuste de targetSdk/compileSdk e de permissões conforme políticas da loja, se houver publicação.
- Opção de ícone próprio em `res` em vez de `sym_def_app_icon`, se for exigência de marca.
- Testes instrumentados (AndroidJUnitRunner) para o envelope e o fluxo de envio.

---

## Histórico de alterações (resumo)

- **1.5 (código 6, publicado):** trava do provedor de licença. O
  `LicencaContentProvider` passa a exigir a permissão de assinatura
  `SMS_INTERNAL` (`readPermission`), então nem o `adb shell content query` lê os
  dados. APK e AAB assinados pela esteira na
  [Release Android 1.5](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.5),
  com o mesmo certificado do 1.4, então instala por cima. O 1.4, também
  publicado, ficou com o provedor exportado e sem permissão de leitura.

- **1.4 (código 5, publicado):** filtro do SMS de licença
  corrigido. Antes o número oficial nunca era preenchido, então qualquer SMS com
  o prefixo gravava a chave; agora `LicenseSms` recusa tudo enquanto o número não
  for salvo no painel, confere o remetente e exige o formato da chave.
  `ConfigActivity` ganhou o campo "Número que envia a licença". Primeiros testes
  automatizados do app (`LicenseSmsTest`, 8 casos, JUnit 4).

- **Ponte com o Gaspar + ponta a ponta (versão em desenvolvimento):**
  `GatewayListenerService` (UDP/TCP), `GatewayCrypto`, `E2ECrypto`,
  `E2EKeySender`, `SmsReceiptSender`, `ScanSetupActivity`, `SetupPayload`,
  `SetupDiagnosticHelper`, `SmsStatusReceiver`, `BootReceiver`; `SendSmsActivity`
  deixou de ser exportada e exige permissão de assinatura; limite de 300 SMS por
  dia no aparelho; logs sem número nem texto. Guia em
  [README-PDV-SMS.md](README-PDV-SMS.md); termo em
  [wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html).

- Alinhamento com CaraCore-PDV (v1.1): marca "CaraCore PDV - Envio SMS"; descrição "o que faz" em linguagem de operação sem internet; cores do header em verde (#059669) alinhadas ao portal; README e STATUS referem Enlace de Contingência; strings e comentários em pt-BR.
- Licença Premium: `SMSReceiver` (CC-LICENSE/CARACORE-KEY, filtro por número oficial), `SmsPreferences` (chave, número oficial, `isLicencaValida()`), `LicencaContentProvider` (hardware_id, chave, valida, mes_ano). `ConfigActivity`: status da licença (vermelho/verde), botão "Verificar Conexão USB". Permissões RECEIVE_SMS e SEND_SMS no Manifest e em runtime.
- Build em `build\` no projeto; `gradle.properties` e `-Dorg.gradle.vfs.watch=false` para reduzir AccessDenied. Basta uma exclusão no Defender: a pasta do projeto.
- `config.bat`: detecção de JDK 11+ (Java, Adoptium, Microsoft, Corretto) e fallback para JDK 8 com aviso.
- `ConfigActivity` como launcher com painel "CaraCore PDV - Envio SMS"; `SendSmsActivity` para intent de envio; `PdvSmsLogger`, `ErrorReporter`, `AppExceptionHandler`; exceções de domínio; ícone padrão; `SmsPreferences` para ativo/pausado.
- `build.bat`: suporte a `bundle` e `aab` (AAB para Play Store), `clean release`, `clean bundle`; correção de erro "foi inesperado neste momento" no CMD (ajustes em echo e em textos com parênteses dentro de blocos if). AAB renomeado para `pdv-sms-enviar-release.aab` em `build\outputs\bundle\release\`.
- Scripts de keystore: `verificar-keystore.bat` (valida senha com keytool -list); `recriar-keystore.bat` (backup do keystore e criação de novo).
- `BackupUpdateReceiver` no Manifest (intent BACKUP_UPDATE).
- `excluir-defender-e-build.ps1`: adiciona pasta do projeto às exclusões do Defender e executa `build.bat clean`; executar como Administrador.
- Remoção de `android.enableR8` do `gradle.properties` global do Gradle (AGP 7+ tornou a opção obsoleta; R8 é o padrão).
