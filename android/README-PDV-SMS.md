# PDV Enviar SMS

Aplicativo Android que serve de **celular de envio** para o PDV, por meio da
ponte local do Gaspar. O app não aceita acionamento por outros aplicativos: ele
fica ouvindo o Gaspar na rede Wi-Fi (`GatewayListenerService`), recebe o pedido
**cifrado de ponta a ponta**, abre com a chave que só ele tem, dispara o SMS pelo
chip e devolve o comprovante. A licença Premium é digitada na tela de
configuração ou aplicada pelo QR de pareamento — o app **não lê SMS** desde a
1.7. Ele expõe ao PDV, via ContentProvider, o HardwareID e o estado da licença.

> **Publicado hoje:** o **1.7 (código 8)**, de 15/11/2026, na
> [Release Android 1.7](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.7).
> Ele retira a leitura de SMS (licença digitada ou pelo QR), retira o pedido de
> isenção da economia de bateria, exige token do PDV no aviso de backup, mostra
> a confirmação só depois do toque na notificação e compila para o Android 15
> (targetSdk/compileSdk 35, AGP 8.7.3, Gradle 8.9, JDK 17). Gate local verde:
> build, 27 testes unitários (10 de confirmação, 3 de QR de Wi‑Fi, 8 da licença
> e 6 do token de backup) e lint sem erros; APK assinado e AAB publicados e
> instalados por cima do 1.6 no emulador. A prova em emulador está registrada em
> [STATUS_ATUAL.md](STATUS_ATUAL.md); falta o teste em celular físico.
>
> O **1.6** e o **1.5** continuam disponíveis nas respectivas releases.

O envio por ADB (`am start -e number -e body`) foi **encerrado**: a activity de
envio não é mais exportada e exige permissão interna de assinatura. O teste
manual agora é feito pela janela **Celular / SMS** do Gaspar.

---

## Requisitos

| Item | Descrição |
|------|-----------|
| JDK 17 ou superior | Android Gradle Plugin 8.7 exige JDK 17+ (não aceita mais JDK 8/11). O config.bat procura JDK 21 e 17. |
| Android SDK | ANDROID_HOME definido ou SDK em %LOCALAPPDATA%\Android\Sdk. Inclui platform-tools (adb) e, para build, platforms;android-35 e build-tools 35.0.0. |
| Celular | Android 7.0 (API 24) ou superior, chip/SIM, depuração USB ativada, cabo USB conectado ao PC. Android 13+ pede também a permissão de notificações. |

Detalhes de instalação: use os atalhos `config.bat`, `build.bat` e `publicar-celular.bat` deste diretório, com JDK 17+ e Android SDK instalados.

---

## Configuração inicial

### Java (JAVA_HOME)

O `config.bat` detecta JDK 17+ automaticamente (C:\Program Files\Java\jdk-21 e jdk-17; Eclipse Adoptium; Amazon Corretto). Se nenhum for encontrado, exibe aviso: o AGP 8.7 exige JDK 17+ e o build vai falhar. JDK 8 e 11 não servem mais.

Para fixar um JDK, edite `config.bat` e defina, por exemplo:

```batch
set "JAVA_HOME=C:\Program Files\Java\jdk-17"
```

Ou copie `config.bat.example` para `config.bat` e ajuste. O config.bat é usado por: build.bat, criar-keystore.bat, verificar-keystore.bat, instalar-gradle-wrapper.bat.

### Android SDK (ANDROID_HOME)

Defina ANDROID_HOME apontando para a raiz do SDK. Se não estiver definido, build.bat e publicar-celular.bat usam %LOCALAPPDATA%\Android\Sdk se existir.

Conteúdo mínimo do SDK (via sdkmanager): platform-tools, platforms;android-35, build-tools;35.0.0. Exemplo:

```batch
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"
```

Para instalar o SDK do zero: use `baixar-dependencias-android.bat` (requer Python 3.6+). Opções: --sdk-root=..., --accept-licenses, --install-cmdline-tools.

### Gradle Wrapper

Se `gradle\wrapper\gradle-wrapper.jar` não existir, o build.bat chama automaticamente `instalar-gradle-wrapper.bat`. Para instalar ou reinstalar manualmente:

```batch
instalar-gradle-wrapper.bat
```

O script usa Gradle em GRADLE_89 (ex.: D:\dev\caracore-pdv\tools\gradle-8.9) se existir bin\gradle.bat; caso contrário, baixa Gradle 8.9. Para outro caminho: defina GRADLE_89 antes de executar.

---

## Build

### APK debug (teste e publicar-celular)

```batch
build.bat
```

O build usa o diretório `build\` no projeto. O APK fica em `build\outputs\apk\debug\pdv-sms-enviar-1.7.apk` para scripts como publicar-celular.bat.

O script: aplica config.bat para JAVA_HOME; verifica ANDROID_HOME; chama instalar-gradle-wrapper.bat se o jar do wrapper não existir; executa gradlew --stop, gradlew assembleDebug --no-build-cache --max-workers=1 -Dorg.gradle.vfs.watch=false.

### APK release (assinado, Play Store ou distribuição)

Exige `keystore.properties` com storeFile, storePassword, keyAlias e keyPassword. Veja a seção Assinatura release.

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

O clean executa gradlew --stop, gradlew clean e remove `build\`. Se AccessDenied persistir, feche o Android Studio e rode `build.bat clean` de novo. Como último recurso, o administrador da máquina pode liberar a pasta do projeto no painel do antivírus instalado — o projeto não traz nem executa nenhum script para isso.

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

## Wi‑Fi da loja (1.6)

No painel, o cartão **Wi‑Fi da loja** guarda o nome e a senha da rede da loja no
próprio celular, cifrados com uma chave do Android Keystore
(`WifiCredentialStore`). O painel **Abrir painel do Wi‑Fi** permite:

1. **Guardar** o nome (SSID) e a senha do roteador (8 a 63 caracteres). O app
   não altera o roteador.
2. **Mostrar** ou **copiar** a senha somente depois da confirmação do dono
   (digital, rosto ou PIN/senha do celular). A senha na tela some em 30 segundos
   e a cópia em 60 segundos. Em celular sem trava, o app recusa revelar.
3. **Gerar QR** no formato `WIFI:` para outro aparelho entrar na rede; o QR some
   em 60 segundos.
4. **Testar ligação** com o computador do PDV (conexão TCP ao host/porta do
   pareamento), mostrando o tempo de resposta ou a orientação quando não há
   resposta.

O recurso depende de o celular ter trava (PIN, senha ou biometria). A senha não
sai do aparelho: não há envio para servidor nenhum.

---

## Confirmação de operações no celular (1.6)

Com o switch **Receber pedidos de confirmação** ligado, o computador pode pedir
ao celular a aprovação de **desconto**, **cancelamento** ou **sangria**. O
pedido chega pela porta 49998, já cifrado pelo segredo do pareamento, no comando:

```json
{"action":"confirmar_operacao","id":"c-001","tipo":"desconto",
 "referencia":"VENDA-1234","valor":1500,"motivo":"cliente pediu",
 "prazo":120}
```

- `valor` em centavos, até R$ 100.000,00; `prazo` em segundos, de 30 a 900.
- O celular recusa pedido repetido (`id` já visto), fora das regras ou com o
  switch desligado, e responde no ack com o motivo.
- Aceito o pedido, o celular mostra uma **notificação**; a tela de confirmação
  abre quando o dono toca na notificação. Desde a 1.7 não há mais tela cheia
  sobre a tela de bloqueio nem a permissão `USE_FULL_SCREEN_INTENT`.
- **Aprovar** exige digital, rosto ou PIN/senha do celular. **Negar** pede uma
  confirmação simples. O prazo aparece em contagem regressiva; vencido, o pedido
  é registrado como expirado.
- A decisão fica no histórico do aparelho (**Ver histórico**) e é devolvida
  cifrada em `POST /api/mobile/confirmacao` com `{"id","status","metodo"}`.
  Se o computador estiver desligado, a decisão fica guardada e é reenviada
  quando ele voltar a responder.
- **Pedido de teste** cria um pedido local (marcado como teste) para exercitar a
  tela sem o computador; nada é enviado.

O lado do computador — enviar o pedido e receber a decisão — faz parte da
próxima etapa do Gaspar/PDV e ainda não está implementado. O histórico do
celular guarda as últimas 100 decisões.

---

## Aviso de backup do PDV (1.7)

O PDV avisa o celular quando o backup termina, por um broadcast do Android
(`br.com.caracore.pdv.sms.BACKUP_UPDATE`). Desde a 1.7 esse broadcast é
**protegido por token**: sem o token, o aviso é recusado.

1. Abra o painel do app. O cartão **Backup do banco de dados** mostra o token do
   aparelho (32 caracteres hexadecimais, criado na primeira abertura) e o botão
   **Copiar token do backup**.
2. O PDV precisa endereçar o broadcast ao app (**`-p`**) e incluir o token no
   extra `token`, junto com `timestamp` e `status`:

```batch
adb shell am broadcast -p br.com.caracore.pdv.sms -a br.com.caracore.pdv.sms.BACKUP_UPDATE --es token <token> --es timestamp <YYYY_MM_DD_HH_MM_SS> --es status OK
```

O `-p` é obrigatório: a partir do Android 8, broadcast implícito para app em
segundo plano é bloqueado pelo sistema ("Background execution not allowed") e o
aviso nunca chega. Medido no emulador Android 13: sem `-p` o receptor não roda;
com `-p` e token certo grava `last_backup_timestamp`/`last_backup_status`; com
`-p` e token errado não grava nada.

O app compara o token recebido com o guardado usando comparação de tempo
constante. Token ausente ou errado gera a linha "Aviso de backup recusado:
token ausente ou invalido." no log e nada é gravado; token certo grava a data,
a hora e o status do último backup como antes.

**Compatibilidade:** o PDV que ainda não envia o token continua funcionando com
o app **1.6 publicado**; com a **1.7**, o aviso de backup desse PDV será
recusado até o PDV ser atualizado para mandar `-p br.com.caracore.pdv.sms` e
`--es token`. O código do PDV (projeto separado) fica em
`AdbSmsProvider.sendBackupUpdateBroadcast`.

---

## Licença Premium e exposição para o PDV

Licença Premium sem SMS (a partir da 1.7): o app **não lê SMS**. A chave
(`CC-AAAAmm-{hex8}`) é aplicada de duas formas:

1. **Digitada no painel**: o cartão **Licença** tem o campo da chave e o botão
   **Salvar chave**. O texto é normalizado por `LicenseSms.chaveDe`: aceita a
   chave pura, o prefixo `CC-LICENSE:` / `CARACORE-KEY:` em qualquer caixa e
   espaços em volta; o que não casar com `CC-\d{6}-[0-9a-fA-F]{8}` é recusado
   com aviso e nada é gravado.
2. **Pelo QR de configuração**: o QR gerado pelo Gaspar pode trazer a chave, que
   é aplicada junto com IP, porta e segredo.

A chave fica em `SmsPreferences` e `isLicencaValida()` exige mês atual ou
futuro. O status aparece em vermelho ("Licença Gratuita / Inativa") ou em verde
("Licença Premium Ativa") no painel. O botão "Verificar Conexão USB" consulta
`adb_enabled` e indica se a depuração USB está ativa para o PDV.

O app deixou de ter o campo "Número que envia a licença" e o receptor de SMS;
quem atualiza do 1.6 para a 1.7 precisa digitar a chave uma vez (a chave que já
estava salva continua valendo).

Consulta protegida (a partir do 1.5, publicado): o ContentProvider `licenca` exige a permissão de assinatura `br.com.caracore.pdv.sms.permission.SMS_INTERNAL`. Só um aplicativo assinado com a mesma chave deste app lê `hardware_id` (ANDROID_ID), `chave`, `valida` (1 ou 0) e `mes_ano` (YYYYMM extraído da chave). O `adb shell content query` deixa de responder: o shell não tem essa permissão. O APK do 1.4 publicado na [Release Android 1.4](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.4) **não** tem essa trava: nele o provedor está exportado e sem permissão de leitura, medido no APK baixado da release.

O PDV 4.1.0 não consulta esse provedor — ele decide o plano Premium pela licença assinada da máquina (`LicencaPro`), não pela chave que chega por SMS ao celular. A exposição foi mantida apenas como recurso interno, restrito aos apps da Cara Core assinados com a mesma chave.

---

## Permissão de SMS

Na primeira abertura o app solicita **SEND_SMS** e, no Android 13 ou superior,
**POST_NOTIFICATIONS**. Desde a 1.7 ele **não pede RECEIVE_SMS nem READ_SMS**:
não recebe nem consulta mensagens — a licença é digitada ou vem pelo QR. Toque
em Permitir.

O envio normal vem do Gaspar pela rede Wi-Fi, não de outro aplicativo. Não é
preciso liberar nada além dessas permissões. A isenção da economia de bateria
**não é mais solicitada**: se quiser, o dono ajusta o app para "Sem restrições"
nas configurações do Android.

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
- **Senha do Wi‑Fi (1.6)**: guardada cifrada com chave do Android Keystore; só é
  mostrada/copiada/convertida em QR depois da confirmação do dono, some da tela
  e da área de transferência sozinha, e o app recusa revelar em celular sem
  trava.
- **Aviso de backup (1.7)**: o broadcast `BACKUP_UPDATE` só grava estado quando
  traz o token de 32 caracteres gerado no painel; a comparação é de tempo
  constante. É a única entrada exportada além do despertar por reinício.
- **Confirmação de operações (1.6/1.7)**: o pedido chega cifrado pelo segredo do
  pareamento, com prazo curto, valor máximo e recusa de repetição; aprovar exige
  digital, rosto ou PIN/senha do próprio celular, e a decisão volta cifrada. A
  partir da 1.7 a tela só abre depois do toque na notificação.

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
    res/values/strings.xml, colors.xml, styles.xml
    res/layout/activity_config.xml, activity_wifi.xml, activity_confirmation.xml
    res/drawable/bg_header.xml, bg_card.xml, bg_chip.xml, gaspar_mascote.png
    res/mipmap-*/ic_launcher*.png, res/mipmap-anydpi-v26/ic_launcher*.xml
  README.md
  STATUS_ATUAL.md
```
---

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

---

## Referências

- [README.md](README.md) – visão rápida do aplicativo e da ponte com o Gaspar.
- [STATUS_ATUAL.md](STATUS_ATUAL.md) – status atual da aplicação e evolução.
- [Variáveis de ambiente do Android (ANDROID_HOME)](https://developer.android.com/studio/command-line/variables)
- [sdkmanager](https://developer.android.com/studio/command-line/sdkmanager)
- [Assinatura de apps Android](https://developer.android.com/studio/publish/app-signing)
