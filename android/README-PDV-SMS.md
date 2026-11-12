# PDV Enviar SMS

Aplicativo Android que serve de **celular de envio** para o PDV, por meio da
ponte local do Gaspar. O app não aceita acionamento por outros aplicativos: ele
fica ouvindo o Gaspar na rede Wi-Fi (`GatewayListenerService`), recebe o pedido
**cifrado de ponta a ponta**, abre com a chave que só ele tem, dispara o SMS pelo
chip e devolve o comprovante. Também recebe SMS de ativação de licença Premium
(CC-LICENSE ou CARACORE-KEY) e expõe ao PDV, via ContentProvider, o HardwareID e
o estado da licença.

> Este código é o **1.5**, ainda sem release. O aplicativo publicado é o **1.4**,
> com o envelope de ponta a ponta e o filtro do SMS de licença pelo número
> oficial. O 1.5 acrescenta a trava do provedor de licença (`readPermission` de
> assinatura), que o 1.4 publicado não tem.

O envio por ADB (`am start -e number -e body`) foi **encerrado**: a activity de
envio não é mais exportada e exige permissão interna de assinatura. O teste
manual agora é feito pela janela **Celular / SMS** do Gaspar.

---

## Requisitos

| Item | Descrição |
|------|-----------|
| JDK 11 ou superior | Android Gradle Plugin 7.4.2 exige JDK 11+. O config.bat detecta JDK 11, 17 ou 21. |
| Android SDK | ANDROID_HOME definido ou SDK em %LOCALAPPDATA%\Android\Sdk. Inclui platform-tools (adb) e, para build, platforms;android-33 e build-tools. |
| Celular | Android 7.0 (API 24) ou superior, chip/SIM, depuração USB ativada, cabo USB conectado ao PC. |

Detalhes de instalação: use os atalhos `config.bat`, `build.bat` e `publicar-celular.bat` deste diretório, com JDK 11+ e Android SDK instalados.

---

## Configuração inicial

### Java (JAVA_HOME)

O `config.bat` detecta JDK 11+ automaticamente (C:\Program Files\Java\jdk-17, jdk-21, jdk-11; Eclipse Adoptium; Microsoft; Amazon Corretto). Se nenhum for encontrado, usa JDK 8 e exibe aviso: o AGP 7.4.2 exige JDK 11+ e o build pode falhar.

Para fixar um JDK, edite `config.bat` e defina, por exemplo:

```batch
set "JAVA_HOME=C:\Program Files\Java\jdk-17"
```

Ou copie `config.bat.example` para `config.bat` e ajuste. O config.bat é usado por: build.bat, criar-keystore.bat, verificar-keystore.bat, instalar-gradle-wrapper.bat.

### Android SDK (ANDROID_HOME)

Defina ANDROID_HOME apontando para a raiz do SDK. Se não estiver definido, build.bat e publicar-celular.bat usam %LOCALAPPDATA%\Android\Sdk se existir.

Conteúdo mínimo do SDK (via sdkmanager): platform-tools, platforms;android-33, build-tools (ex.: 33.0.2). Exemplo:

```batch
sdkmanager "platform-tools" "platforms;android-33" "build-tools;33.0.2"
```

Para instalar o SDK do zero: use `baixar-dependencias-android.bat` (requer Python 3.6+). Opções: --sdk-root=..., --accept-licenses, --install-cmdline-tools.

### Gradle Wrapper

Se `gradle\wrapper\gradle-wrapper.jar` não existir, o build.bat chama automaticamente `instalar-gradle-wrapper.bat`. Para instalar ou reinstalar manualmente:

```batch
instalar-gradle-wrapper.bat
```

O script usa Gradle em GRADLE_7_5 (ex.: D:\dev\caracore-pdv\tools\gradle-7.5) se existir bin\gradle.bat; caso contrário, baixa Gradle 7.5. Para outro caminho: defina GRADLE_7_5 antes de executar.

---

## Build

### APK debug (teste e publicar-celular)

```batch
build.bat
```

O build usa o diretório `build\` no projeto. O APK fica em `build\outputs\apk\debug\pdv-sms-enviar-1.5.apk` para scripts como publicar-celular.bat.

O script: aplica config.bat para JAVA_HOME; verifica ANDROID_HOME; chama instalar-gradle-wrapper.bat se o jar do wrapper não existir; executa gradlew --stop, gradlew assembleDebug --no-build-cache --max-workers=1 -Dorg.gradle.vfs.watch=false.

### APK release (assinado, Play Store ou distribuição)

Exige `keystore.properties` com storeFile, storePassword, keyAlias e keyPassword. Veja a seção Assinatura release.

```batch
build.bat release
```

O APK é gerado em `build\outputs\apk\release\pdv-sms-enviar-1.5-release.apk`.

### AAB para Play Store (bundle)

Exige `keystore.properties` configurado (mesma seção Assinatura release).

```batch
build.bat bundle
```

Ou, como alias:

```batch
build.bat aab
```

O AAB é gerado em `build\outputs\bundle\release\pdv-sms-enviar-release.aab`. Para limpar antes: `build.bat clean bundle`.

### Build com limpeza (evitar AccessDenied em .dex)

Se houver AccessDeniedException em SendSmsActivity.dex, rode:

```batch
build.bat clean
```

Ou para release:

```batch
build.bat clean release
```

O clean executa gradlew --stop, gradlew clean e remove `build\`. Se AccessDenied persistir: adicione a pasta do projeto às Exclusões do Defender (interface do Windows ou `Add-MpPreference -ExclusionPath "CAMINHO_DO_PROJETO"` em PowerShell como Administrador); ou execute `excluir-defender-e-build.ps1` como Administrador (adiciona a exclusão e executa `build.bat clean`).

---

## Instalação no celular

Conecte o celular por USB com Depuração USB ativada. No celular, aceite "Permitir depuração USB" (e "Sempre permitir" se existir).

```batch
publicar-celular.bat
```

O script: valida ANDROID_HOME e adb; gera o APK com build.bat se o APK debug não existir; verifica dispositivo em state=device (adb devices) e Android API >= 24; tenta desativar verifier_verify_adb_installs e package_verifier_enable; instala com adb install -r; em falha, tenta adb install -r -t e, se precisar, adb push + pm install -r -t.

Log: `publicar-celular.log` na pasta do script.

Se adb devices mostrar offline: desligue e reconecte o cabo; aceite "Permitir depuração USB"; em Opções do desenvolvedor, "Revogar autorizações de depuração USB" e reconecte. Tente também: adb kill-server e adb start-server.

Se mostrar unauthorized: no celular deve aparecer "Permitir depuração USB?". Toque em Permitir. Se não aparecer: desbloqueie a tela, reconecte o cabo ou revogue as autorizações em Opções do desenvolvedor e reconecte.

Se a instalação falhar com INSTALL_FAILED_VERIFICATION_FAILURE: desative temporariamente o Play Protect (Google, Segurança, Verificação de apps); ou copie o APK para o celular e instale abrindo o arquivo; em aparelhos com root pode-se tentar: adb shell settings put global verifier_verify_adb_installs 0 e package_verifier_enable 0.

---

## Verificar se o app está funcionando

Com o celular conectado por USB e o app instalado:

```batch
verificar-app.bat
```

Verifica: dispositivo conectado e autorizado (adb devices com linha terminando em "device"); app br.com.caracore.pdv.sms instalado; permissão SEND_SMS concedida (dumpsys package). Encerra com código 0 se tudo OK, 1 se algo falhar.

O envio de teste **não** é mais feito por ADB. Abra o Gaspar, entre em
**Celular / SMS** e use **Enviar teste**; o pedido chega cifrado ao celular e o
resultado aparece na lista **Últimos envios**.

Alternativa para conceder SEND_SMS sem abrir o app (em muitos dispositivos funciona):

```batch
adb shell pm grant br.com.caracore.pdv.sms android.permission.SEND_SMS
```

---

## Enviar SMS pelo PC

O acionamento externo por ADB foi desativado de propósito, para que o celular
não vire máquina de SMS. O caminho normal é:

1. O Gaspar está aberto no computador, com **Ponte ativa**.
2. O celular está na mesma Wi-Fi e pareado (chave pública registrada).
3. O PDV (ou o **Enviar teste** do painel) entrega o pedido ao Gaspar.
4. O Gaspar cifra com a chave do celular e envia pela porta 49998.

Não existe mais um comando para disparar SMS direto pelo PC: quem precisa testar
o aparelho usa a janela **Celular / SMS** do Gaspar.

---

## Licença Premium e exposição para o PDV

Recepção de licença por SMS: o `SMSReceiver` escuta SMS com "CC-LICENSE:[CHAVE]" ou "CARACORE-KEY:[CHAVE]" no corpo e aplica a regra de `LicenseSms`. Com o número oficial gravado em `SmsPreferences` (campo "Número que envia a licença"), só SMS desse remetente são aceitos; **sem esse número, nenhum SMS de licença é aceito**. A chave é guardada e validada no formato CC-YYYYMM-{hex8} (YYYYMM deve ser maior ou igual ao mês atual).

Na tela de configuração: o status da licença aparece em vermelho ("Licença Gratuita / Inativa") ou em verde ("Licença Premium Ativa"), conforme `isLicencaValida()`. O botão "Verificar Conexão USB" consulta `adb_enabled` e indica se a depuração USB está ativa para o PDV.

Consulta protegida (este código, 1.5, ainda sem release): o ContentProvider `licenca` exige a permissão de assinatura `br.com.caracore.pdv.sms.permission.SMS_INTERNAL`. Só um aplicativo assinado com a mesma chave deste app lê `hardware_id` (ANDROID_ID), `chave`, `valida` (1 ou 0) e `mes_ano` (YYYYMM extraído da chave). O `adb shell content query` deixa de responder: o shell não tem essa permissão. O APK do 1.4 publicado na [Release Android 1.4](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.4) **não** tem essa trava: nele o provedor está exportado e sem permissão de leitura, medido no APK baixado da release.

O PDV 4.1.0 não consulta esse provedor — ele decide o plano Premium pela licença assinada da máquina (`LicencaPro`), não pela chave que chega por SMS ao celular. A exposição foi mantida apenas como recurso interno, restrito aos apps da Cara Core assinados com a mesma chave.

---

## Permissão de SMS

Na primeira abertura o app solicita SEND_SMS e RECEIVE_SMS. O app usa
SEND_SMS para enviar e RECEIVE_SMS para receber a chave de licença; **não
consulta a caixa de entrada** nem lê mensagens antigas, e por isso não pede
READ_SMS. Toque em Permitir.

O envio normal vem do Gaspar pela rede Wi-Fi, não de outro aplicativo. Não é
preciso liberar nada além dessas permissões.

---

## Segurança

- **Envelope de ponta a ponta**: o app cria um par de chaves EC P-256 no primeiro
  uso. A privada fica protegida pelo Android Keystore e nunca sai do aparelho; a
  pública vai ao Gaspar no pareamento. Cada pedido é aberto com AES-256-GCM e só
  vale para o `id` daquele pedido.
- **Sem acionamento externo**: a activity de envio não é exportada e exige
  permissão interna de assinatura; o serviço que escuta a rede também não é
  exportado. Nenhum aplicativo instalado no celular consegue mandar SMS por ele.
- **Limites no aparelho**: 300 SMS por dia, recusa de `id` repetido e de
  sequência repetida, além de exigir o app **ativo**.
- **Sem conteúdo nos logs**: o app registra estado e erros técnicos, sem número e
  sem texto. O SMS enviado fica na caixa **Enviadas** do aplicativo de mensagens,
  como qualquer SMS.
- **Segredo de pareamento**: quem tem o QR pode parear um aparelho. Não tire foto
  do QR nem compartilhe o código; se desconfiar, pareie de novo pelo Gaspar.

O termo completo, com o que é guardado e os limites, está em
[wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html).

---

## Assinatura release

### 1. Criar o keystore

```batch
criar-keystore.bat
```

Gera `pdv-sms-release.keystore` e o alias `pdv-sms` (RSA 2048, validade 10000 dias). Use uma senha segura. O keytool pede senha e dados do certificado (nome, organização, etc.).

Se o keystore já existir, o script avisa e não sobrescreve. Apague o arquivo se quiser criar outro.

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

Caminhos em storeFile são relativos ao diretório android-sms-enviar ou absolutos. Não versionar keystore.properties nem o .keystore (inclua no .gitignore).

Para validar a senha do keystore antes do build:

```batch
verificar-keystore.bat
```

O script pede a senha e executa `keytool -list`. Se o alias `pdv-sms` for exibido, a senha está correta. Se o build release ou bundle ainda falhar, verifique espaços, BOM ou encoding em `keystore.properties` (ANSI ou UTF-8 sem BOM).

Se a senha foi esquecida ou o keystore está corrompido, use `recriar-keystore.bat`: renomeia o keystore atual para `.bak` e chama `criar-keystore.bat`. Use apenas para app novo; apps já publicados na Play Store precisam do mesmo keystore para atualização.

### 3. Build release

```batch
build.bat release
```

Para AAB (Play Store): `build.bat bundle` ou `build.bat aab`. Saída: `build\outputs\bundle\release\pdv-sms-enviar-release.aab`.

---

## Estrutura do projeto

```
android-sms-enviar/
  build.bat                     build APK debug, release ou AAB (Gradle); build em build\
  config.bat                    JAVA_HOME; auto-detecta JDK 11+ ou fallback JDK 8
  config.bat.example            modelo para config.bat
  criar-keystore.bat            gera pdv-sms-release.keystore
  recriar-keystore.bat          backup do keystore e cria novo; só para app novo
  verificar-keystore.bat        valida senha do keystore com keytool -list
  instalar-gradle-wrapper.bat   instala gradle-wrapper.jar (Gradle 7.5)
  publicar-celular.bat          instala APK via adb; valida dispositivo, API 24+
  verificar-app.bat             verifica: dispositivo, app instalado, permissão SEND_SMS
  excluir-defender-e-build.ps1  adiciona pasta às exclusões do Defender e executa build.bat clean; executar como Admin
  baixar-dependencias-android.bat  chama script Python para baixar platform-tools, platforms, build-tools
  baixar-dependencias-android.py
  build.gradle                  build em build\ (pasta do projeto)
  gradle.properties             org.gradle.workers.max=1, org.gradle.parallel=false
  settings.gradle
  gradlew, gradlew.bat
  keystore.properties.example   copiar para keystore.properties e preencher
  gradle/wrapper/
  src/main/
    AndroidManifest.xml         ConfigActivity (launcher), ScanSetupActivity (QR),
                                SendSmsActivity (interna), GatewayListenerService,
                                SMSReceiver, SmsStatusReceiver, BootReceiver,
                                BackupUpdateReceiver, LicencaContentProvider
    java/br/com/caracore/pdv/sms/
      PdvSmsApp.java, ConfigActivity.java, ScanSetupActivity.java
      GatewayListenerService.java, GatewayCrypto.java, E2ECrypto.java, E2EKeySender.java
      SmsReceiptSender.java, SmsStatusReceiver.java, SendSmsActivity.java
      SetupPayload.java, SetupDiagnosticHelper.java, SmsPreferences.java
      SMSReceiver.java, BootReceiver.java, BackupUpdateReceiver.java
      LicencaContentProvider.java, PdvSmsLogger.java, ErrorReporter.java,
      AppExceptionHandler.java, excecoes (SmsSendException, SmsValidationException, etc.)
    res/values/strings.xml, colors.xml
    res/layout/activity_config.xml
    res/drawable/bg_header.xml, bg_card.xml
  README.md
  STATUS_ATUAL.md
```
---

## Erros comuns

| Erro | Causa ou solução |
|------|------------------|
| Java não encontrado / AGP exige JDK 11 | Instale JDK 11 ou 17 (ex.: Eclipse Adoptium). Ajuste config.bat com o caminho em JAVA_HOME. |
| ANDROID_HOME não definido | Defina a variável para a raiz do Android SDK ou instale em %LOCALAPPDATA%\Android\Sdk. |
| gradle-wrapper.jar não encontrado | Execute instalar-gradle-wrapper.bat. O build.bat tenta chamá-lo automaticamente. |
| aapt2 / no repositories | Em settings.gradle deve haver dependencyResolutionManagement com repositories { google(); mavenCentral() }. |
| keytool não reconhecido | Use criar-keystore.bat, que usa %JAVA_HOME%\bin\keytool. |
| Keystore was tampered with or password incorrect (release/bundle) | Execute verificar-keystore.bat para validar a senha. Confira storePassword e keyPassword em keystore.properties (sem espaços antes/depois do =). Salve em ANSI ou UTF-8 sem BOM. |
| adb: device offline | Desconecte e reconecte o cabo; aceite "Permitir depuração USB"; tente adb kill-server e adb start-server. |
| device unauthorized | No celular, toque em Permitir em "Permitir depuração USB?". Se não surgir, desbloqueie a tela, reconecte ou revogue autorizações em Opções do desenvolvedor. |
| INSTALL_FAILED_VERIFICATION_FAILURE | Desative Play Protect ou instale o APK manualmente (copiar para o aparelho e abrir o arquivo). |
| AccessDeniedException em SendSmsActivity.dex | O build usa build\ no projeto. Rode build.bat clean e em seguida build.bat. Se persistir: adicione a pasta do projeto às Exclusões do Defender (interface ou Add-MpPreference -ExclusionPath "CAMINHO_PROJETO" em PowerShell como Admin), ou execute excluir-defender-e-build.ps1 como Administrador. |
| APK vazio ou muito pequeno | Verifique ANDROID_HOME e se existem platforms e build-tools. Tente: gradlew clean assembleDebug --no-build-cache. |

---

## Referências

- [README.md](README.md) – visão rápida do aplicativo e da ponte com o Gaspar.
- [STATUS_ATUAL.md](STATUS_ATUAL.md) – status atual da aplicação e evolução.
- [Variáveis de ambiente do Android (ANDROID_HOME)](https://developer.android.com/studio/command-line/variables)
- [sdkmanager](https://developer.android.com/studio/command-line/sdkmanager)
- [Assinatura de apps Android](https://developer.android.com/studio/publish/app-signing)
