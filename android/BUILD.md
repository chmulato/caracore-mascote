# Compilar, assinar e instalar o app do celular

Referência de ambiente, build, assinatura, instalação por cabo e erros
conhecidos do aplicativo Android da loja. O que conversa com quem usa o
aplicativo está em [README-PDV-SMS.md](README-PDV-SMS.md); a visão de cada
versão está em [STATUS_ATUAL.md](STATUS_ATUAL.md). O conteúdo abaixo foi transferido
do README sem perda de comando ou de caminho. A seção do painel de Wi-Fi foi conferida
e reescrita contra o código do aplicativo em 23/11/2026.

## Requisitos

| Item | Descrição |
|------|-----------|
| JDK 17 ou superior | Android Gradle Plugin 8.7 exige JDK 17+ (não aceita mais JDK 8/11). O config.bat procura JDK 21 e 17. |
| Android SDK | ANDROID_HOME definido ou SDK em %LOCALAPPDATA%\Android\Sdk. Inclui platform-tools (adb) e, para build, platforms;android-35 e build-tools 35.0.0. |
| Celular | Android 7.0 (API 24) ou superior, chip/SIM, depuração USB ativada, cabo USB conectado ao PC. Android 13+ pede também a permissão de notificações. |

Detalhes de instalação: use os atalhos `config.bat`, `build.bat` e
`publicar-celular.bat` deste diretório, com JDK 17+ e Android SDK instalados.

## Configuração inicial

### Java (JAVA_HOME)

O `config.bat` detecta JDK 17+ automaticamente (C:\Program Files\Java\jdk-21 e
jdk-17; Eclipse Adoptium; Amazon Corretto). Se nenhum for encontrado, exibe aviso:
o AGP 8.7 exige JDK 17+ e o build vai falhar. JDK 8 e 11 não servem mais.

Para fixar um JDK, edite `config.bat` e defina, por exemplo:

```batch
set "JAVA_HOME=C:\Program Files\Java\jdk-17"
```

Ou copie `config.bat.example` para `config.bat` e ajuste. O config.bat é usado por:
build.bat, criar-keystore.bat, verificar-keystore.bat, instalar-gradle-wrapper.bat.

### Android SDK (ANDROID_HOME)

Defina ANDROID_HOME apontando para a raiz do SDK. Se não estiver definido,
build.bat e publicar-celular.bat usam %LOCALAPPDATA%\Android\Sdk se existir.

Conteúdo mínimo do SDK (via sdkmanager): platform-tools, platforms;android-35,
build-tools;35.0.0. Exemplo:

```batch
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"
```

Para instalar o SDK do zero: use `baixar-dependencias-android.bat` (requer Python
3.6+). Opções: --sdk-root=..., --accept-licenses, --install-cmdline-tools.

### Gradle Wrapper

Se `gradle\wrapper\gradle-wrapper.jar` não existir, o build.bat chama
automaticamente `instalar-gradle-wrapper.bat`. Para instalar ou reinstalar
manualmente:

```batch
instalar-gradle-wrapper.bat
```

O script usa Gradle em GRADLE_89 (ex.: D:\dev\caracore-pdv\tools\gradle-8.9) se
existir bin\gradle.bat; caso contrário, baixa Gradle 8.9. Para outro caminho:
defina GRADLE_89 antes de executar.

## Build

O projeto usa Android Gradle Plugin 8.7.3, Gradle 8.9, compileSdk/targetSdk 35 e
exige JDK 17 ou superior.

### APK debug (teste e publicar-celular)

```batch
build.bat
```

O build usa o diretório `build\` no projeto. O APK fica em
`build\outputs\apk\debug\pdv-sms-enviar-1.7.apk` para scripts como
publicar-celular.bat.

O script: aplica config.bat para JAVA_HOME; verifica ANDROID_HOME; chama
instalar-gradle-wrapper.bat se o jar do wrapper não existir; executa gradlew
--stop, gradlew assembleDebug --no-build-cache --max-workers=1
-Dorg.gradle.vfs.watch=false.

### APK release (assinado, Play Store ou distribuição)

Exige `keystore.properties` com storeFile, storePassword, keyAlias e keyPassword.
Veja a seção Assinatura release.

```batch
build.bat release
```

O APK é gerado em `build\outputs\apk\release\pdv-sms-enviar-1.7-release.apk`.

### AAB para Play Store (bundle)

Exige `keystore.properties` configurado (mesma seção Assinatura release).

```batch
build.bat bundle
```

Ou, como alias:

```batch
build.bat aab
```

O AAB é gerado em `build\outputs\bundle\release\pdv-sms-enviar-release.aab`. Para
limpar antes: `build.bat clean bundle`.

### Build com limpeza (evitar AccessDenied em .dex)

Se houver AccessDeniedException em SendSmsActivity.dex, rode:

```batch
build.bat clean
```

Ou para release:

```batch
build.bat clean release
```

O clean executa gradlew --stop, gradlew clean e remove `build\`. Se AccessDenied
persistir, feche o Android Studio e rode `build.bat clean` de novo. Como último
recurso, o administrador da máquina pode liberar a pasta do projeto no painel do
antivírus instalado — o projeto não traz nem executa nenhum script para isso.

## Instalação no celular por cabo

Conecte o celular por USB com Depuração USB ativada. No celular, aceite "Permitir
depuração USB" (e "Sempre permitir" se existir).

```batch
publicar-celular.bat
```

O script: valida ANDROID_HOME e adb; gera o APK com build.bat se o APK debug não
existir; verifica dispositivo em state=device (adb devices) e Android API >= 24;
tenta desativar verifier_verify_adb_installs e package_verifier_enable; instala com
adb install -r; em falha, tenta adb install -r -t e, se precisar, adb push + pm
install -r -t.

Log: `publicar-celular.log` na pasta do script.

Se adb devices mostrar offline: desligue e reconecte o cabo; aceite "Permitir
depuração USB"; em Opções do desenvolvedor, "Revogar autorizações de depuração
USB" e reconecte. Tente também: adb kill-server e adb start-server.

Se mostrar unauthorized: no celular deve aparecer "Permitir depuração USB?". Toque
em Permitir. Se não aparecer: desbloqueie a tela, reconecte o cabo ou revogue as
autorizações em Opções do desenvolvedor e reconecte.

Se a instalação falhar com INSTALL_FAILED_VERIFICATION_FAILURE: desative
temporariamente o Play Protect (Google, Segurança, Verificação de apps); ou copie
o APK para o celular e instale abrindo o arquivo.

## Conferir se o app está funcionando

Com o celular conectado por cabo e o app instalado:

```batch
verificar-app.bat
```

Verifica: dispositivo conectado e autorizado (adb devices com linha terminando em
"device"); app br.com.caracore.pdv.sms instalado; permissão SEND_SMS concedida
(dumpsys package). Encerra com código 0 se tudo OK, 1 se algo falhar.

O envio de teste **não** é feito por cabo. Abra o Gaspar, entre em **Celular /
SMS** e use **Enviar teste**; o pedido chega cifrado ao celular e o resultado
aparece na lista **Últimos envios**.

Alternativa para conceder SEND_SMS sem abrir o app (em muitos dispositivos
funciona):

```batch
adb shell pm grant br.com.caracore.pdv.sms android.permission.SEND_SMS
```

## Caminho do pedido e contrato do pareamento

O acionamento externo por cabo foi desativado de propósito: o envio por
`adb shell am start -e number -e body` não funciona mais porque a activity de envio
deixou de ser exportada e passou a exigir a permissão de assinatura interna. O caminho
normal é:

1. O Gaspar está aberto no computador, com **Ponte ativa**.
2. O celular está na mesma rede e pareado (chave pública registrada).
3. O PDV (ou o **Enviar teste** do painel) entrega o pedido ao Gaspar.
4. O Gaspar fecha o pedido com a chave do celular e envia pela porta TCP **49998**
   (a descoberta do aparelho usa UDP **49999**).

O comando que o celular espera, já descifrado do envelope:

```json
{"action":"confirmar_operacao","id":"c-001","tipo":"desconto",
 "referencia":"VENDA-1234","valor":1500,"motivo":"cliente pediu",
 "prazo":120}
```

- `valor` em centavos, até R$ 100.000,00; `prazo` em segundos, de 30 a 900.
- O celular recusa pedido repetido (`id` já visto), fora das regras ou com o
  switch desligado, e responde no ack com o motivo.
- A decisão volta cifrada em `POST /api/mobile/confirmacao` com
  `{"id","status","metodo"}`.

O aviso de fim de backup é um broadcast do Android endereçado ao app:

```batch
adb shell am broadcast -p br.com.caracore.pdv.sms -a br.com.caracore.pdv.sms.BACKUP_UPDATE --es token <token> --es timestamp <YYYY_MM_DD_HH_MM_SS> --es status OK
```

O `-p` é obrigatório: a partir do Android 8, broadcast implícito para app em
segundo plano é bloqueado pelo sistema ("Background execution not allowed") e o
aviso nunca chega. Medido no emulador Android 13: sem `-p` o receptor não roda;
com `-p` e token certo grava `last_backup_timestamp`/`last_backup_status`; com
`-p` e token errado não grava nada. O app compara o token com o guardado em
comparação de tempo constante; recusa gera a linha "Aviso de backup recusado:
token ausente ou invalido." no log.

O código do PDV que manda esse aviso (projeto separado) fica em
`AdbSmsProvider.sendBackupUpdateBroadcast`.

## Painel do Wi-Fi da loja

O cartão **Wi-Fi da loja** guarda SSID e senha no próprio aparelho, pela
`WifiCredentialStore`, cifrados com chave do Android Keystore (`AES/GCM`, tag de 128
bits e IV aleatório gravado na frente do blob). As regras medidas no código:

- Senha aceita de **8 a 63 caracteres** (`WifiActivity.java:74`). Fora disso o app
  recusa e nada é gravado.
- Revelar, copiar e gerar QR passam antes por `comAutorizacao`: aparelho sem trava de
  tela (`KeyguardManager.isDeviceSecure`, `WifiActivity.java:121`) recusa, e com trava a
  confirmação sai por `DeviceAuth.confirmar` — biometria ou PIN/senha do próprio celular.
- A senha revelada volta a ficar mascarada em **30 s** (`TEMPO_SENHA_NA_TELA`,
  `WifiActivity.java:37`); a cópia sai da área de transferência em **60 s**
  (`TEMPO_SENHA_COPIADA`), e só quando o conteúdo ainda é aquela senha. No Android 13 ou
  mais novo a cópia vai marcada como sensível (`ClipDescription.EXTRA_IS_SENSITIVE`).
- O QR usa o formato `WIFI:T:WPA;S:<ssid>;P:<senha>;H:false;;` (`WifiQr.java:13`), é
  gerado em 640×640 e se esconde em **60 s**.
- **Testar ligação** abre um TCP ao host e porta do pareamento com prazo de
  **2 500 ms** (`WifiActivity.java:250`) e mostra o tempo gasto; sem conexão ele orienta
  em vez de só falhar.

Nada do painel é enviado para servidor nenhum e o app não altera o roteador.

## Licença Premium e exposição para o PDV

A chave (`CC-AAAAmm-{hex8}`) é aceita de duas formas:

1. **Digitada no painel**: o cartão **Licença** tem o campo da chave e o botão
   **Salvar chave**. O texto é normalizado por `LicenseSms.chaveDe`: aceita a
   chave pura, o prefixo `CC-LICENSE:` / `CARACORE-KEY:` em qualquer caixa e
   espaços em volta; o que não casar com `CC-\d{6}-[0-9a-fA-F]{8}` é recusado com
   aviso e nada é gravado.
2. **Pelo QR de configuração**, aplicada junto com IP, porta e segredo.

A chave fica em `SmsPreferences` e `isLicencaValida()` exige mês atual ou futuro.
O botão "Verificar Conexão USB" consulta `adb_enabled` e indica se a depuração USB
está ativa para o PDV. O app deixou de ter o campo "Número que envia a licença" e
o receptor de SMS.

Consulta protegida (a partir do 1.5, publicado): o ContentProvider `licenca` exige
a permissão de assinatura `br.com.caracore.pdv.sms.permission.SMS_INTERNAL`. Só um
aplicativo assinado com a mesma chave deste app lê `hardware_id` (ANDROID_ID),
`chave`, `valida` (1 ou 0) e `mes_ano` (YYYYMM extraído da chave). O
`adb shell content query` deixa de responder: o shell não tem essa permissão. O
APK do 1.4 publicado na
[Release Android 1.4](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.4)
**não** tem essa trava: nele o provedor está exportado e sem permissão de leitura,
medido no APK baixado da release.

O PDV 4.1.0 não consulta esse provedor — ele decide o plano Premium pela licença
assinada da máquina (`LicencaPro`), não pela chave que chega por SMS ao celular. A
exposição foi mantida apenas como recurso interno, restrito aos apps da Cara Core
assinados com a mesma chave.

## Estado de qualidade da 1.7 publicada

Gate local verde no dia da publicação: build, 27 testes unitários (10 de
confirmação, 3 de QR de Wi-Fi, 8 da licença e 6 do token de backup) e lint sem
erros; APK assinado e AAB publicados e instalados por cima do 1.6 no emulador. A
prova em emulador está registrada em [STATUS_ATUAL.md](STATUS_ATUAL.md); falta o
teste em celular físico.

## Assinatura release

### 1. Criar o keystore

```batch
criar-keystore.bat
```

Gera `pdv-sms-release.keystore` e o alias `pdv-sms` (RSA 2048, validade 10000
dias). Use uma senha segura. O keytool pede senha e dados do certificado (nome,
organização, etc.).

Se o keystore já existir, o script avisa e não sobrescreve. Apague o arquivo se
quiser criar outro. Nenhum keystore, senha ou `keystore.properties` faz parte
deste repositório.

### 2. Configurar keystore.properties

```batch
copy keystore.properties.example keystore.properties
```

Edite `keystore.properties`:

```
storeFile=pdv-sms-release.keystore
storePassword=SUA_SENHA
keyAlias=pdv-sms
keyPassword=SUA_SENHA
```

Caminhos em storeFile são relativos ao diretório android-sms-enviar ou absolutos.
Não versionar keystore.properties nem o .keystore (inclua no .gitignore).

Para validar a senha do keystore antes do build:

```batch
verificar-keystore.bat
```

O script pede a senha e executa `keytool -list`. Se o alias `pdv-sms` for
exibido, a senha está correta. Se o build release ou bundle ainda falhar, verifique
espaços, BOM ou encoding em `keystore.properties` (ANSI ou UTF-8 sem BOM).

Se a senha foi esquecida ou o keystore está corrompido, use `recriar-keystore.bat`:
renomeia o keystore atual para `.bak` e chama `criar-keystore.bat`. Use apenas para
app novo; apps já publicados na Play Store precisam do mesmo keystore para
atualização.

### 3. Build release

```batch
build.bat release
```

Para AAB (Play Store): `build.bat bundle` ou `build.bat aab`. Saída:
`build\outputs\bundle\release\pdv-sms-enviar-release.aab`.

## Estrutura do projeto

```
android-sms-enviar/
  build.bat                     build APK debug, release ou AAB (Gradle); build em build\
  config.bat                    JAVA_HOME; procura JDK 17+ (AGP 8.7 não aceita JDK 8/11)
  config.bat.example            modelo para config.bat
  criar-keystore.bat            gera pdv-sms-release.keystore
  recriar-keystore.bat          backup do keystore e cria novo; só para app novo
  verificar-keystore.bat        valida senha do keystore com keytool -list
  instalar-gradle-wrapper.bat   instala gradle-wrapper.jar (Gradle 8.9)
  publicar-celular.bat          instala APK via adb; valida dispositivo, API 24+
  verificar-app.bat             verifica: dispositivo, app instalado, permissão SEND_SMS
  baixar-dependencias-android.bat  chama script Python para baixar platform-tools, platforms, build-tools
  baixar-dependencias-android.py
  build.gradle                  build em build\ (pasta do projeto)
  gradle.properties             org.gradle.workers.max=1, org.gradle.parallel=false
  settings.gradle
  gradlew, gradlew.bat
  keystore.properties.example   copiar para keystore.properties e preencher
  gradle/wrapper/
  src/main/
    AndroidManifest.xml         ConfigActivity (launcher), WifiActivity,
                                ConfirmationActivity, ScanSetupActivity (QR),
                                SendSmsActivity (interna), GatewayListenerService,
                                SmsStatusReceiver, BootReceiver,
                                BackupUpdateReceiver, LicencaContentProvider
    java/br/com/caracore/pdv/sms/
      PdvSmsApp.java, ConfigActivity.java, ScanSetupActivity.java
      GatewayListenerService.java, GatewayCrypto.java, E2ECrypto.java, E2EKeySender.java
      SmsReceiptSender.java, SmsStatusReceiver.java, SendSmsActivity.java
      SetupPayload.java, SetupDiagnosticHelper.java, SmsPreferences.java
      LicenseSms.java, BackupToken.java, BootReceiver.java, BackupUpdateReceiver.java
      LicencaContentProvider.java, PdvSmsLogger.java, ErrorReporter.java,
      AppExceptionHandler.java, excecoes (SmsSendException, SmsValidationException, etc.)
      WifiActivity.java, WifiCredentialStore.java, WifiQr.java, DeviceAuth.java
      ConfirmationActivity.java, ConfirmationRequest.java, ConfirmationStore.java,
      ConfirmationNotifier.java, ConfirmationResponder.java
      EmailBridge.java, EmailEnvelope.java, EmailPonteServico.java, ImapClient.java, SmtpClient.java
      PareamentoPorOrigem.java
    res/values/strings.xml, colors.xml, styles.xml
    res/layout/activity_config.xml, activity_wifi.xml, activity_confirmation.xml,
      activity_email.xml
    res/drawable/bg_header.xml, bg_card.xml, bg_chip.xml, gaspar_mascote.png
    res/mipmap-*/ic_launcher*.png, res/mipmap-anydpi-v26/ic_launcher*.xml
  README.md
  STATUS_ATUAL.md
```

## Erros comuns

| Erro | Causa ou solução |
|------|------------------|
| Java não encontrado / AGP exige JDK 17 | Instale JDK 17 ou 21 (ex.: Eclipse Adoptium). Ajuste config.bat com o caminho em JAVA_HOME. |
| ANDROID_HOME não definido | Defina a variável para a raiz do Android SDK ou instale em %LOCALAPPDATA%\Android\Sdk. |
| gradle-wrapper.jar não encontrado | Execute instalar-gradle-wrapper.bat. O build.bat tenta chamá-lo automaticamente. |
| aapt2 / no repositories | Em settings.gradle deve haver dependencyResolutionManagement com repositories { google(); mavenCentral() }. |
| keytool não reconhecido | Use criar-keystore.bat, que usa %JAVA_HOME%\bin\keytool. |
| Keystore was tampered with or password incorrect (release/bundle) | Execute verificar-keystore.bat para validar a senha. Confira storePassword e keyPassword em keystore.properties (sem espaços antes/depois do =). Salve em ANSI ou UTF-8 sem BOM. |
| adb: device offline | Desconecte e reconecte o cabo; aceite "Permitir depuração USB"; tente adb kill-server e adb start-server. |
| device unauthorized | No celular, toque em Permitir em "Permitir depuração USB?". Se não surgir, desbloqueie a tela, reconecte ou revogue autorizações em Opções do desenvolvedor. |
| INSTALL_FAILED_VERIFICATION_FAILURE | Desative Play Protect ou instale o APK manualmente (copiar para o aparelho e abrir o arquivo). |
| AccessDeniedException em SendSmsActivity.dex | O build usa build\ no projeto. Rode build.bat clean e em seguida build.bat. Se persistir, feche o Android Studio; como último recurso, o administrador da máquina libera a pasta do projeto no painel do antivírus. |
| APK vazio ou muito pequeno | Verifique ANDROID_HOME e se existem platforms e build-tools. Tente: gradlew clean assembleDebug --no-build-cache. |

## Referências

- [README.md](README.md) – visão do aplicativo para quem usa.
- [STATUS_ATUAL.md](STATUS_ATUAL.md) – status atual da aplicação e evolução.
- [Variáveis de ambiente do Android (ANDROID_HOME)](https://developer.android.com/studio/command-line/variables)
- [sdkmanager](https://developer.android.com/studio/command-line/sdkmanager)
- [Assinatura de apps Android](https://developer.android.com/studio/publish/app-signing)
