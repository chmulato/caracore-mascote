# Status atual - PDV Enviar SMS

Documento de acompanhamento do estado da aplicação e da evolução. Atualizado conforme mudanças relevantes.

> **Medido em 15/11/2026:** o **código deste diretório é a 1.7 (código 8)**,
> preparada e provada localmente e **ainda não publicada**. O que está
> publicado continua sendo a **1.6 (código 7)**, na
> [Release Android 1.6](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.6).
> Gate local verde: build, 27 testes unitários (10 de confirmação, 3 de QR de
> Wi‑Fi, 8 da licença e 6 do token de backup) e lint sem erros. APK debug
> `build\outputs\apk\debug\pdv-sms-enviar-1.7.apk`, 2.456.228 B, SHA-256
> `249244a5…99673a`; manifesto medido no APK: versionCode 8, versão 1.7,
> targetSdk 35 e 9 permissões (sem `RECEIVE_SMS`, sem
> `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, sem `USE_FULL_SCREEN_INTENT`).
> **Exercitado em emulador Android 13 (API 33)**: instalação e abertura, licença
> digitada (chave inválida recusada; chave válida → "Licença Premium Ativa"),
> pedido de permissão de SMS seguido do de notificações **um depois do outro**,
> aviso de backup aceito com o token certo e ignorado com token errado ou sem
> token, pedido de confirmação chegando só como aviso e abrindo a tela ao toque
> (sem abrir sozinho e sem abrir por cima da tela bloqueada), botão de bateria
> abrindo a lista do sistema (app não isento) e versão "1.7" no painel.
> O envio de SMS, a biometria de digital, a notificação com a tela bloqueada, o
> QR lido pela câmera e o lado do computador seguem **não exercitados**.

---

## Propósito

Celular de envio do PDV pela ponte local do Gaspar. O app escuta a rede Wi-Fi
(`GatewayListenerService`), recebe o pedido **cifrado de ponta a ponta**, abre
com a chave privada que só ele tem, dispara o SMS pelo chip e devolve o
comprovante ao Gaspar. O acionamento por intent/ADB foi encerrado: a activity de
envio não é exportada e exige permissão interna de assinatura.

O mesmo celular também guarda a senha do Wi‑Fi da loja e serve como
**confirmação de operações sensíveis** do PDV (desconto, cancelamento e sangria),
com digital, rosto ou senha do aparelho.

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
- **Painel Wi‑Fi da loja** (`WifiActivity`): guarda nome e senha da rede da loja
  cifrados por chave do Android Keystore (`WifiCredentialStore`); mostra e copia
  a senha somente depois da confirmação do dono (digital/rosto ou PIN do
  aparelho, `DeviceAuth` + `androidx.biometric`); a senha na tela some em 30 s e
  a cópia em 60 s; gera QR no formato `WIFI:` (`WifiQr`) para outro aparelho
  entrar; testa se o computador do PDV responde (TCP no host/porta do
  pareamento). Não altera o roteador.
- **Confirmação no celular** (`ConfirmationActivity`): o comando
  `confirmar_operacao` na porta 49998 aceita desconto, cancelamento e sangria
  (`ConfirmationRequest`), com prazo de 30 a 900 s, valor até R$ 100.000,00 e
  identificador único (anti-repetição em `ConfirmationStore`); mostra um aviso
  de alta prioridade **sem abrir a tela sozinho** (`ConfirmationNotifier`, sem
  `fullscreenIntent`) e a tela abre quando o dono toca no aviso; aprova com
  biometria/PIN e nega com confirmação; registra histórico no aparelho; devolve
  a decisão cifrada em `POST /api/mobile/confirmacao`
  (`ConfirmationResponder`), com reenvio automático quando o computador volta a
  responder. O switch "Receber pedidos de confirmação" liga/desliga o recurso; o
  botão **Pedido de teste** exercita a tela sem o computador.
- Painel de controle (launcher): `ConfigActivity` com cabeçalho do mascote
  Gaspar e verde da marca, texto em linguagem simples, switch para ativar/pausar
  o envio, cartões de Wi‑Fi, de confirmação e de **backup do banco de dados**,
  status da licença (vermelho/verde), campo para digitar a chave da licença com
  o botão "Salvar chave", token do backup com o botão "Copiar token do backup" e
  o botão "Verificar Conexão USB".
- Licença Premium **digitada no painel**: a chave é colada ou digitada no campo
  e salva pelo botão; `LicenseSms.chaveDe` normaliza e confere o formato
  CC-AAAAmm-{hex8} e `isLicencaValida()` exige mês atual ou futuro. O app **não
  lê mais SMS** e a permissão `RECEIVE_SMS` foi removida; o receptor de SMS de
  licença (`SMSReceiver`) também. Quem já tinha licença salva continua com ela.
  O pareamento por QR continua podendo levar a chave.
- **Aviso de backup protegido por token**: `BackupUpdateReceiver` só grava
  `last_backup_timestamp`/`last_backup_status` quando o aviso chega
  **endereçado ao app** (`-p br.com.caracore.pdv.sms`) e traz o token mostrado no
  painel (`BackupToken`, 32 caracteres hexadecimais, comparado com
  `MessageDigest.isEqual`). Token errado ou ausente não grava nada.
- Exposição para o PDV: `LicencaContentProvider` (authority
  `br.com.caracore.pdv.sms.licenca`) com `hardware_id` (ANDROID_ID), `chave`,
  `valida` e `mes_ano`. Protegido por `readPermission` de assinatura
  (`SMS_INTERNAL`) — só app assinado com a mesma chave lê, e o
  `adb shell content query` deixa de responder. O PDV 4.1.0 não consulta o
  provedor; o plano dele vem de `LicencaPro`.
- **Sem acionamento externo**: `SendSmsActivity` é interna (`exported=false` +
  permissão de assinatura) e o serviço de rede não é exportado. `WifiActivity` e
  `ConfirmationActivity` também não são exportadas.
- Permissões: SEND_SMS (envio), INTERNET, CAMERA (QR), FOREGROUND_SERVICE,
  FOREGROUND_SERVICE_REMOTE_MESSAGING, POST_NOTIFICATIONS (pedida no Android 13+,
  uma caixa por vez, depois da de SMS), RECEIVE_BOOT_COMPLETED, USE_BIOMETRIC e
  USE_FINGERPRINT. **Não** pede isenção de bateria e **não** usa aviso de tela
  cheia.
- Tratamento de exceções: `PdvSmsLogger` (tag PdvSms), `ErrorReporter`,
  `AppExceptionHandler`; exceções de domínio em `SmsSendException`,
  `SmsPermissionException`, `SmsDisabledException`, `SmsValidationException` e
  `PdvSmsException`.
- Ícone: mascote Gaspar em `mipmap-*` (legado, redondo e adaptativo) e skin
  clara com verde da marca (`AppTheme`). Label: "CaraCore PDV - Envio SMS".
- Build: Gradle (AGP 8.7.3, Gradle 8.9), saída em `build\`; `config.bat` procura
  JDK 17+; `build.bat` aceita debug, `release`, `bundle`/`aab`, `clean`;
  `instalar-gradle-wrapper.bat` monta o wrapper a partir do Gradle 8.9.
- Instalação: `publicar-celular.bat`. Verificação: `verificar-app.bat`
  (dispositivo, app e SEND_SMS; o teste de envio é feito no Gaspar). Assinatura:
  `criar-keystore.bat`, `verificar-keystore.bat`, `recriar-keystore.bat`.

---

## Pilha técnica

- Android: minSdk 24, targetSdk 35, compileSdk 35. Versão 1.7 (código 8).
- Java 8 (source/target). JDK 17 para o build (AGP 8.7.3).
- Gradle 8.9, Android Gradle Plugin 8.7.3.
- Janela normal (não ocupa as bordas da tela) mesmo com alvo 35
  (`tools:targetApi="35"` no tema).
- Dependências: `androidx.core:core:1.6.0`,
  `androidx.biometric:biometric:1.1.0`,
  `com.journeyapps:zxing-android-embedded:4.3.0` e `junit:junit:4.13.2` (teste).
- Declara que precisa de telefonia (`android.hardware.telephony`,
  `required=true`), então aparelhos sem chip não veem o app nas lojas.
- Atividades: `ConfigActivity` (MAIN/LAUNCHER), `WifiActivity`,
  `ConfirmationActivity`, `ScanSetupActivity` (QR), `SendSmsActivity` (interna,
  não exportada). `PdvSmsApp` como Application.
- Componentes: `GatewayListenerService` (UDP 49999 + TCP 49998),
  `SmsStatusReceiver` (aceito/entregue), `BootReceiver`,
  `BackupUpdateReceiver`, `LicencaContentProvider`.
- Criptografia: `GatewayCrypto` (canal AES-GCM com o segredo do pareamento),
  `E2ECrypto` (envelope por pedido) e `WifiCredentialStore` (AES-GCM com chave
  do Android Keystore para a senha do Wi‑Fi).
- Permissões: SEND_SMS, INTERNET, CAMERA, FOREGROUND_SERVICE,
  FOREGROUND_SERVICE_REMOTE_MESSAGING, POST_NOTIFICATIONS,
  RECEIVE_BOOT_COMPLETED, USE_BIOMETRIC, USE_FINGERPRINT.

---

## Build e implantação

- Desenvolvimento: `build.bat` (debug), `build.bat release` (com keystore.properties). `build.bat bundle` ou `build.bat aab` (AAB para Play Store). `build.bat clean` para limpar e evitar AccessDenied em .dex. Combinações: `build.bat clean release`, `build.bat clean bundle`.
- APK debug: `build\outputs\apk\debug\pdv-sms-enviar-1.7.apk`. APK release: `build\outputs\apk\release\pdv-sms-enviar-1.7-release.apk`. AAB: `build\outputs\bundle\release\pdv-sms-enviar-release.aab`.
- Instalação em dispositivo: `publicar-celular.bat`. Requer ANDROID_HOME, adb, dispositivo em state=device, API >= 24. Na primeira execução, aceitar as permissões de SMS e, no Android 13+, as de notificações.
- Assinatura release e AAB: `criar-keystore.bat` gera `pdv-sms-release.keystore` e alias `pdv-sms`. `keystore.properties` (storeFile, storePassword, keyAlias, keyPassword). `verificar-keystore.bat` valida a senha com keytool -list. `recriar-keystore.bat` renomeia o keystore antigo para .bak e chama `criar-keystore.bat`; usar apenas para app novo, não para atualização na loja.
- Android SDK: `sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"`.

---

## Limitações conhecidas

- **Medido em emulador, não em celular real**: a 1.7 foi exercitada em emulador
  Android 13 (licença digitada, permissões, aviso de backup com token,
  confirmação só ao toque e painel) e verificada por compilação, 27 testes
  unitários, lint e inspeção do APK. Ficam pendentes de aparelho físico: envio
  real de SMS com chip, biometria de digital, notificação com a tela bloqueada e
  leitura do QR pela câmera.
- **Lado do computador pendente**: o Gaspar/PDV ainda não envia
  `confirmar_operacao` nem recebe `/api/mobile/confirmacao`. Enquanto isso, a
  confirmação pratica só o fluxo local pelo botão **Pedido de teste**; o teste
  de ligação do painel Wi‑Fi só mede alcance TCP até o endereço do pareamento.
- **PDV precisa mandar o token do backup**: o aviso de backup da 1.7 só é
  aceito quando chega endereçado ao app (`-p br.com.caracore.pdv.sms`) e com o
  token do painel. Um PDV antigo continua funcionando com a 1.6 publicada, mas
  na 1.7 o aviso dele é recusado até o PDV ser atualizado (projeto separado,
  `AdbSmsProvider.sendBackupUpdateBroadcast`).
- **Proteção da senha do Wi‑Fi**: o texto fica cifrado por chave do Keystore, e o
  app só a devolve depois da confirmação do dono (`senha(context, true)`), mas a
  trava é de tela: um aparelho sem PIN/senha/biometria não é aceito para revelar
  a senha. Não há vínculo de hardware exigindo autenticação a cada leitura.
- AccessDenied em .dex no Windows: em alguns ambientes (antivírus, IDE) o erro pode ocorrer. Mitigações: `build.bat clean`, fechar o Android Studio, `--max-workers=1`, `org.gradle.workers.max=1`. Como último recurso, o administrador da máquina libera a pasta do projeto no painel do antivírus; o repositório não traz script que altere o antivírus.
- Envio depende de chip/SIM e permissão SEND_SMS. O switch **App ativo** é
  checado no serviço de rede; pedido com o app pausado é recusado com aviso.
- Sem o Gaspar pareado e com chave registrada, o celular não recebe pedido: o
  Gaspar recusa enfileirar (`e2e_required`).
- Play Protect pode bloquear instalação via adb (INSTALL_FAILED_VERIFICATION_FAILURE). Contornar: desativar temporariamente ou instalar o APK manualmente.
- Sem ofuscação nem minify no release (minifyEnabled false).
- `allowBackup="false"` no manifest: as preferências não vão para o backup do
  Google. A chave privada do envelope fica presa ao Keystore e não funciona em
  outro aparelho; o segredo do pareamento deve ser trocado pareando de novo.

---

## Possível evolução

- Implementar no Gaspar/PDV o envio de `confirmar_operacao` e a rota
  `/api/mobile/confirmacao`, com prazo e trilha de auditoria no computador, e o
  envio do token no aviso de backup.
- Testar em aparelho real: biometria, PIN, SMS com chip, QR lido por outro
  celular, notificação com tela bloqueada e reenvio da decisão com o PC
  desligado.
- Logs opcionais em arquivo (sem número nem texto) para diagnóstico em campo.
- Ofuscação/minify no release e testes instrumentados (AndroidJUnitRunner) para
  o envelope e o fluxo de envio.
- Publicação em loja, se houver, ajustando o que a política exigir.

---

## Histórico de alterações (resumo)

- **1.7 (código 8, preparada em 15/11/2026, não publicada):** licença digitada
  no painel em vez de lida por SMS (permissão e receptor de SMS removidos);
  isenção de bateria deixada de pedir (o botão abre a lista do sistema); aviso
  de backup só aceito com token e endereçado ao app; confirmação de operações
  chegando só como aviso e abrindo a tela ao toque (sem tela cheia por cima do
  bloqueio); alvo Android atualizado para 35 (AGP 8.7.3, Gradle 8.9, JDK 17).
  Corrigido no caminho: os pedidos de permissão de SMS e de notificações
  concorriam, e o Android 13 descartava o segundo — agora são sequenciais. Gate
  local: build, 27 testes unitários (10 de confirmação, 3 de QR de Wi‑Fi,
  8 da licença e 6 do token de backup) e lint verdes; APK debug 2.456.228 B
  (SHA-256 `249244a5…99673a`) provado em emulador Android 13.

- **1.6 (código 7, publicado em 13/11/2026):** ícone do mascote
  Gaspar (legado, redondo e adaptativo) e skin clara com verde da marca; painel
  Wi‑Fi da loja com senha cifrada no Keystore, revelação/cópia/QR protegidos por
  digital ou PIN e teste de ligação com o computador; confirmação de desconto,
  cancelamento e sangria no celular, com prazo, anti-repetição, histórico,
  notificação de tela cheia e devolução cifrada da decisão. Gate local: build,
  21 testes e lint verdes; APK debug medido e exercitado em emulador Android 13,
  que apontou e já corrigiu dois acabamentos: valor em pt‑BR (R$ 15,00) e
  registro do método efetivo de aprovação no histórico (PIN × biometria). APK
  assinado (2.099.052 B, SHA-256 `76acbc6b…7ad1`) e AAB (1.915.879 B, SHA-256
  `b2a9b4e3…c89a`) publicados na Release Android 1.6; o APK de release instalou
  por cima do 1.5 e repetiu a aprovação por PIN.

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
- Build em `build\` no projeto; `gradle.properties` e `-Dorg.gradle.vfs.watch=false` para reduzir AccessDenied. A pasta do projeto já cobre `build\`.
- `config.bat`: detecção de JDK 11+ (Java, Adoptium, Microsoft, Corretto) e fallback para JDK 8 com aviso.
- `ConfigActivity` como launcher com painel "CaraCore PDV - Envio SMS"; `SendSmsActivity` para intent de envio; `PdvSmsLogger`, `ErrorReporter`, `AppExceptionHandler`; exceções de domínio; ícone padrão; `SmsPreferences` para ativo/pausado.
- `build.bat`: suporte a `bundle` e `aab` (AAB para Play Store), `clean release`, `clean bundle`; correção de erro "foi inesperado neste momento" no CMD (ajustes em echo e em textos com parênteses dentro de blocos if). AAB renomeado para `pdv-sms-enviar-release.aab` em `build\outputs\bundle\release\`.
- Scripts de keystore: `verificar-keystore.bat` (valida senha com keytool -list); `recriar-keystore.bat` (backup do keystore e criação de novo).
- `BackupUpdateReceiver` no Manifest (intent BACKUP_UPDATE).
- Remoção de `android.enableR8` do `gradle.properties` global do Gradle (AGP 7+ tornou a opção obsoleta; R8 é o padrão).
