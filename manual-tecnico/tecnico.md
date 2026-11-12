# Guia técnico do Gaspar

Documentação para quem mantém, compila ou audita o Gaspar. O guia do usuário está no [README](../README.md).

- Branch oficial: **master**
- Versão: **1.7.2**
- Licença: **MIT**
- Plataformas: **Windows 10/11** e **Linux (X11/XWayland)**

## Stack

- Python 3.10 ou superior (testado com 3.13)
- Tkinter/ttk
- Pillow
- pyautogui
- psutil
- pystray
- cryptography (AES-256-GCM da ponte de SMS)
- qrcode (QR de pareamento do celular)

No Linux, instale também `python3-tk`, `libx11-6`, `libxext6`, `libxtst6` e `libxss1`.

O aplicativo Android da pasta `android/` é Java, sem Kotlin, com minSdk 24, targetSdk 27, compileSdk 33, Gradle 7.5 e Android Gradle Plugin 7.4.2.

## Arquitetura

| Módulo | Responsabilidade |
| --- | --- |
| `gaspar/__init__.py` | Nome, empresa e versão. |
| `gaspar/__main__.py` | Entrada `python -m gaspar`. |
| `gaspar/activity.py` | Detecção de ausência do usuário e de tela cheia. |
| `gaspar/app.py` | Painel principal, bandeja, preferências e orquestração. |
| `gaspar/autostart.py` | Início automático no Windows e no Linux. |
| `gaspar/blackbox.py` | Interface do Gaspar BlackBox. |
| `gaspar/config.py` | Preferências, limites e persistência. |
| `gaspar/eventlog.py` | Log com rotação. |
| `gaspar/overlay.py` | Mascote flutuante, transparência, click-through e z-order. |
| `gaspar/paths.py` | Ativos e pasta de dados do usuário. |
| `gaspar/presence.py` | Motor de simulação de presença. |
| `gaspar/sms/audit.py` | Trilha de auditoria LGPD só com metadados, retenção e expurgo. |
| `gaspar/sms/bridge.py` | Regras de envio, limites, fila, repetição e deduplicação por venda. |
| `gaspar/sms/client.py` | Conexão TCP com o aplicativo Android e leitura do recibo. |
| `gaspar/sms/config.py` | Configuração da ponte, segredos, chaves públicas e token da API. |
| `gaspar/sms/crypto.py` | Derivação da chave compartilhada e AES-256-GCM do canal. |
| `gaspar/sms/discovery.py` | Descoberta do celular na rede local (UDP). |
| `gaspar/sms/e2e.py` | Envelope de ponta a ponta: ECDH P-256, HKDF-SHA256, AES-256-GCM e rótulos HMAC. |
| `gaspar/sms/network.py` | Descoberta do IP local do computador. |
| `gaspar/sms/protocol.py` | Formato do anúncio, do comando e do enquadramento TCP. |
| `gaspar/sms/qr.py` | Geração do QR Code de pareamento. |
| `gaspar/sms/server.py` | API HTTP local para o PDV e recepção do diagnóstico do celular. |
| `gaspar/sms/signing.py` | Assinatura HMAC-SHA256 dos pedidos e cache de nonces. |
| `gaspar/sms/store.py` | Fila, histórico e relatórios; guarda o envelope, não o conteúdo. |
| `gaspar/sms/templates.py` | Modelos de mensagem transacionais e validação das variáveis. |
| `gaspar/telemetry_hosts.py` | Bloqueio de telemetria no arquivo `hosts`. |
| `gaspar/tray.py` | Ícone da bandeja. |
| `gaspar/updates.py` | Canal de atualização: assinatura Ed25519, consulta periódica e instalação no Windows. |

## Estrutura do repositório

```text
.
├── android/                       # aplicativo Android que envia os SMS
│   ├── src/                       # código Java, manifesto e recursos
│   ├── gradle/                    # wrapper do Gradle
│   ├── build.gradle
│   ├── settings.gradle
│   ├── pom.xml
│   ├── build.bat                  # debug, release, bundle e clean
│   ├── publicar-celular.bat       # instala o APK via adb
│   ├── verificar-app.bat          # dispositivo, app e permissão SEND_SMS
│   ├── criar-keystore.bat         # assinatura release
│   ├── keystore.properties.example
│   └── README.md
├── assets/
│   ├── gaspar.png                 # imagem oficial (512 px, transparência real)
│   ├── gaspar.ico                 # ícone 16..256 px
│   ├── gaspar_flutuando.gif       # animação de flutuação (220x220)
│   └── gaspar-update-public.pem   # chave pública Ed25519 do canal
├── docs/                          # loja publicada (só o comercial)
│   ├── assets/
│   ├── CNAME
│   ├── index.html
│   └── atualizacao.html
├── manual-tecnico/
│   └── tecnico.md                 # este guia
├── gaspar/
│   ├── __init__.py
│   ├── __main__.py
│   ├── activity.py
│   ├── app.py
│   ├── autostart.py
│   ├── blackbox.py
│   ├── config.py
│   ├── eventlog.py
│   ├── overlay.py
│   ├── paths.py
│   ├── presence.py
│   ├── sms/                       # ponte local de SMS
│   │   ├── __init__.py
│   │   ├── audit.py               # trilha LGPD só com metadados
│   │   ├── bridge.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── crypto.py
│   │   ├── discovery.py
│   │   ├── e2e.py                 # envelope de ponta a ponta
│   │   ├── network.py
│   │   ├── protocol.py
│   │   ├── qr.py
│   │   ├── server.py
│   │   ├── signing.py             # assinatura HMAC dos pedidos
│   │   ├── store.py
│   │   └── templates.py           # modelos de mensagem
│   ├── telemetry_hosts.py
│   ├── tray.py
│   └── updates.py                 # canal de atualização
├── release/
│   └── channel.json               # configuração do canal
├── packaging/
│   ├── windows/
│   │   ├── build_windows.py
│   │   ├── gaspar.iss
│   │   ├── gaspar.spec
│   │   ├── gaspar_blackbox.spec
│   │   └── version_info.txt
│   └── linux/
│       ├── build_linux.sh
│       ├── gaspar.desktop
│       ├── gaspar-blackbox.desktop
│       ├── gaspar.spec
│       └── gaspar_blackbox.spec
├── tests/
│   ├── smoke_test.py              # 5 verificações de fumaça
│   ├── test_isolamento.py         # 2 testes de isolamento das integrações
│   ├── test_channel.py            # 12 testes da rotina de release
│   ├── test_sms.py                # 59 testes da ponte
│   └── test_updates.py            # 27 testes do canal
├── tools/
│   ├── gaspar_channel.py          # init-key, sign, prova, check e verify
│   └── make_assets.py
├── .github/workflows/
│   ├── android.yml
│   ├── channel.yml
│   └── gaspar.yml
├── run.py
├── run_blackbox.py
├── requirements.txt
├── requirements-dev.txt
├── LICENSE
└── README.md
```

## Rodar a partir do código

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
python run.py
```

Opções:

```bash
python run.py --minimized    # abre direto na bandeja
python run.py --version      # mostra a versão
python -m gaspar             # equivalente a run.py
python run_blackbox.py       # abre o BlackBox diretamente
```

O BlackBox pede elevação: UAC no Windows, `pkexec` no Linux. Sem privilégios de administrador ele não altera o arquivo `hosts`.

## Como a transparência e o click-through funcionam

### Windows

1. A janela usa `overrideredirect(True)`, `-topmost` e `-toolwindow`.
2. `-transparentcolor "#ff00ff"` remove o fundo magenta.
3. Via `ctypes`, são aplicados `WS_EX_LAYERED`, `WS_EX_TRANSPARENT` e `WS_EX_NOACTIVATE`.
4. `SetLayeredWindowAttributes(hwnd, 0x00FF00FF, alpha, LWA_COLORKEY | LWA_ALPHA)` combina a chave de cor com a opacidade.
5. `WS_EX_TRANSPARENT` faz o clique atravessar o mascote.
6. `WS_EX_NOACTIVATE` impede que a janela roube o foco.
7. Enquanto o painel está aberto, o overlay é posicionado abaixo da janela principal; ao fechar, volta ao topo.

### Linux

1. A janela continua sem bordas.
2. Cada quadro do GIF gera uma máscara 1-bit com a silhueta do Gaspar.
3. A extensão Shape do X11 (`XShapeCombineMask`) recorta o retângulo de fundo.
4. `XShapeCombineRectangles` com região vazia faz os cliques atravessarem o mascote.
5. A opacidade é aplicada com `-alpha` do Tk.
6. O Tk 8.6 ignora `-topmost` no X11. O mascote é override-redirect e fica acima das janelas gerenciadas pelo gerenciador de janelas; com o painel aberto ele é reempilhado logo abaixo do quadro do painel via Xlib.
7. Ao consultar a janela ativa, o Xlib encerraria o processo se ela já tivesse fechado (`BadWindow`); essas leituras de tela cheia ignoram o erro e seguem sem o dado.

Em Wayland puro, o recorte e o click-through do X11 não se aplicam; rode a sessão com XWayland ou use X11. A detecção de ausência e de tela cheia também depende de APIs do Windows ou do X11; quando indisponível, o app registra um aviso e usa apenas o intervalo configurado.

## Build no Windows

Pré-requisitos:

- Python 3.10+ 64 bits com Tkinter
- Dependências de desenvolvimento: `python -m pip install -r requirements-dev.txt`
- Inno Setup 6 (somente para gerar o instalador): <https://jrsoftware.org/isdl.php>

Comandos:

```bat
python packaging\windows\build_windows.py
python packaging\windows\build_windows.py --no-installer
python packaging\windows\build_windows.py --app-only
python packaging\windows\build_windows.py --blackbox-only
python packaging\windows\build_windows.py --installer-only
```

Saídas:

- `dist/windows/gaspar/gaspar.exe`
- `dist/windows/gaspar_blackbox/gaspar_blackbox.exe`
- `dist/installer/GasparSetup-1.7.2.exe` (quando o Inno Setup está instalado)

O instalador:

- Instala em `{autopf}\Cara Core\Gaspar`; na instalação por usuário isso resolve para `%LOCALAPPDATA%\Programs\Cara Core\Gaspar`.
- Oferece atalho na Área de Trabalho (opcional).
- Oferece início com o Windows (opcional, marcado como não).
- Registra o desinstalador.
- Inclui o Gaspar e o Gaspar BlackBox.
- O BlackBox pede elevação na execução; o Gaspar não precisa de administrador.

Para indicar um `ISCC.exe` fora do caminho padrão:

```bat
set INNO_SETUP_ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
python packaging\windows\build_windows.py
```

Os executáveis não são assinados digitalmente. O SmartScreen pode exibir um aviso na primeira execução; isso é esperado em builds locais.

## Build no Linux

Pacotes Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk python3-dev \
  dpkg-dev libx11-6 libxext6 libxtst6 libxss1 policykit-1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

O `appimagetool` é opcional e necessário apenas para o AppImage. Baixe em <https://github.com/AppImage/appimagetool/releases> e informe o caminho:

```bash
export APPIMAGETOOL=/caminho/para/appimagetool
```

Comandos:

```bash
bash packaging/linux/build_linux.sh
bash packaging/linux/build_linux.sh --deb-only
bash packaging/linux/build_linux.sh --appimage-only
bash packaging/linux/build_linux.sh --skip-pyinstaller
```

Saídas:

- `dist/linux/gaspar/gaspar`
- `dist/linux/gaspar_blackbox/gaspar_blackbox`
- `dist/linux/gaspar_1.7.2_<arch>.deb`
- `dist/linux/Gaspar-1.7.2-<arch>.AppImage`

Instalação do `.deb`:

```bash
sudo apt install ./dist/linux/gaspar_1.7.2_amd64.deb
gaspar
gaspar-blackbox
```

O `.deb` instala:

- `/opt/caracore/gaspar`
- `/opt/caracore/gaspar_blackbox`
- `/usr/bin/gaspar`
- `/usr/bin/gaspar-blackbox`
- entradas de menu `gaspar.desktop` e `gaspar-blackbox.desktop`

AppImage:

```bash
chmod +x dist/linux/Gaspar-1.7.2-amd64.AppImage
./dist/linux/Gaspar-1.7.2-amd64.AppImage
```

O AppImage inclui o Gaspar e o BlackBox. O item **Gaspar BlackBox** do ícone da bandeja encontra o executável na própria instalação.

## Gaspar BlackBox

O BlackBox grava um bloco delimitado no arquivo `hosts`:

```text
# BLOCK TELEMETRIA - INICIO (Cara Core Black-Box)
0.0.0.0 vortex.data.microsoft.com
...
# BLOCK TELEMETRIA - FIM
```

- 34 domínios de telemetria (Microsoft, VS Code/Cursor, Azure e Application Insights).
- Aplicação idempotente: reaplicar não duplica o bloco.
- Remoção restaura o conteúdo original e preserva o estilo de quebra de linha.
- Atualização do cache DNS por `ipconfig`, `resolvectl`, `systemd-resolve` ou `nscd`, conforme disponível.
- Requer administrador/root.
- Reversível pelo botão **Remover bloqueio**.

Interface:

- Abra pelo item **Gaspar BlackBox** no ícone da bandeja do Gaspar.
- Ou use o atalho **Gaspar BlackBox** no Windows/Linux.
- O programa pede elevação sozinho.

CLI:

```bash
python -m gaspar.telemetry_hosts --status
python -m gaspar.telemetry_hosts --dry-run
python -m gaspar.telemetry_hosts --remove
```

O `--dry-run` não altera o arquivo e não exige administrador.

### Isolamento das integrações do PDV

O Gaspar não abre conexão com o Mercado Pago (`api.mercadopago.com`) nem com o PlugNotas/Tecnospeed (`api.plugnotas.com.br`, `api.sandbox.plugnotas.com.br`). Suas únicas saídas são o canal de atualização (`api.caracore.com.br` e `gaspar.caracore.com.br`) e a ponte local de SMS.

O BlackBox altera somente o arquivo `hosts`, com domínios exatos de telemetria da Microsoft. Nenhum endereço de pagamento ou nota está na lista, e não há regra de proxy, DNS ou firewall. O teste `tests/test_isolamento.py` falha se um domínio protegido aparecer na lista de bloqueio ou no código do pacote.

Atenção: o bloqueio inclui domínios de login e marketplace da Microsoft (`login.microsoftonline.com`, `vscode.dev`, `marketplace.visualstudio.com`). Isso pode impedir autenticação ou instalação de extensões enquanto o bloqueio estiver ativo. O guia completo, com configurações de telemetria do VS Code/Cursor, extensões e firewall, está em [wiki.caracore.com.br/gaspar/blackbox.html](https://wiki.caracore.com.br/gaspar/blackbox.html).

## Ponte local de SMS

O PDV não fala com o celular diretamente. O caminho é:

```text
PDV  --HTTP localhost-->  Gaspar (ponte)  --TCP na Wi-Fi-->  app Android  -->  chip/SMS
                                  ^
                                  +-- HTTP: diagnóstico do celular no pareamento
```

Nada sai para a internet: a API escuta na rede local, o PDV pode chamar por `127.0.0.1` e o celular precisa estar na mesma rede Wi-Fi.

### Janela Celular / SMS

O botão **Celular / SMS** abre uma janela separada (o painel principal não foi alterado). Ela mostra o estado do celular, a caixa **Ponte ativa**, **Procurar celular**, **Parear celular**, envio de teste, endereço/token da API e os últimos envios. A ponte só sobe quando **Ponte ativa** está marcada e o app é iniciado; no teste de fumaça ela fica desligada para não abrir porta nem disparar aviso do firewall.

### Pareamento

O QR contém uma linha com seis campos separados por `|`:

```text
CARACORE-SETUP|<ip_do_pc>|<porta_http>|<chave_b64>|<token_de_setup>|<licenca>
```

- `ip_do_pc`: IP da rede local, obtido em `gaspar/sms/network.py` (conexão UDP para 8.8.8.8, sem enviar dados, com fallback pelo hostname).
- `porta_http`: porta da API local (padrão 8766).
- `chave_b64`: segredo compartilhado de 32 bytes, gerado com `os.urandom` e guardado em `sms_config.json`.
- `token_de_setup`: token de uso único, válido por 15 minutos; o app o envia no diagnóstico e ele é apagado em seguida.
- `licenca`: opcional, repassada ao app quando existir.

O app lê o QR, aplica IP, porta, chave e licença, testa permissões de SMS e otimização de bateria e faz `POST /api/mobile/diagnostic`. O Gaspar confere o token, grava o resultado do diagnóstico e conclui o pareamento. O mesmo token não pode ser usado duas vezes.

No primeiro uso o app cria um par de chaves **EC P-256** (a privada fica protegida pelo Android Keystore) e envia a **chave pública** no campo `phone_public_key` do diagnóstico. Essa chave é a ponta do envelope descrito abaixo. Um celular já pareado publica a mesma chave em `POST /api/mobile/key`, então atualizar o APK não exige reler o QR. Trocar uma chave já registrada só é aceito na rota do diagnóstico (com o token de pareamento), o que impede que alguém com o segredo da rede coloque outro aparelho no lugar.

### Descoberta do celular (UDP)

- Porta 49999, com broadcast para `255.255.255.255` e para os endereços de broadcast das interfaces (via `psutil`).
- O Gaspar envia `CARACORE-PDV-DISCOVER`.
- O app responde `CARACORE-APK|<ip>|<porta>`; o Gaspar guarda o IP e a porta em `sms_config.json`.
- Se a descoberta falhar, o pareamento por QR continua sendo a via principal, porque o app também informa o endereço do Gaspar.

### Envio (TCP + AES-256-GCM + envelope de ponta a ponta)

- Porta 49998 no celular.
- Cada mensagem é um quadro: 4 bytes de tamanho em big-endian, seguidos do texto cifrado do canal.
- O texto cifrado é `IV de 12 bytes + AESGCM(...)`, com tag de 128 bits.
- O conteúdo é o JSON `{"action":"send_sms","envelope":"...","id":"...","ts":...,"seq":N,"base":"http://ip:8766"}` em UTF-8. O campo `base` atualiza no celular o endereço do Gaspar para devolver o comprovante.
- A chave do canal é derivada do segredo do QR: decodifica o base64; se o resultado tiver menos de 32 bytes, aplica SHA-256; usa os primeiros 32 bytes. A mesma regra está em `gaspar/sms/crypto.py` e no `GatewayCrypto` do app Android.
- O `envelope` é o conteúdo real e **só o celular abre**: `base64(chave_efêmera(65) || IV(12) || AESGCM(numero||mensagem))`. A chave vem de ECDH P-256 entre uma chave efêmera do Gaspar e a chave pública do celular, passada por HKDF-SHA256 (salt `gaspar-sms-e2e-v1`, info `pdv-phone`). O AAD é o `id` do pedido, então o envelope não pode ser reaproveitado em outro pedido.
- Com `e2e_required` ligado (padrão), pedido sem a chave do celular é recusado com `400` e a mensagem pede novo pareamento. Com `e2e_required` desligado, o campo `number`/`message` volta a viajar no comando, apenas dentro do canal AES — é o modo antigo, para celular sem a versão com envelope.
- O aplicativo publicado (1.2) não envia a chave pública; o código de `android/` já é o 1.3, ainda sem release. Por isso o Gaspar 1.7.1, com `e2e_required` no padrão, recusa o envio até o celular estar pareado com o 1.3. Quem depende de SMS hoje permanece no Gaspar 1.7.0 com o aplicativo 1.2.
- O celular responde na mesma conexão um quadro cifrado com `{"ok":true,"id":"...","status":"aceito","key":"<chave publica>"}` ou `{"ok":false,"error":"..."}`. O Gaspar espera essa resposta por até 0,8 s; ausência não invalida o envio. A `key` só é aceita para preencher a chave quando ainda não existe nenhuma registrada.
- O resultado final chega depois por `POST /api/mobile/receipt`, com o corpo JSON `{"id","status","detail","ts"}` cifrado em AES-GCM e codificado em base64. `status` é `sent`, `delivered` ou `failed`; a autenticação é a própria chave do pareamento, não o token da API.
- Estados do pedido: `fila`, `enviando`, `enviado` (chip aceitou ou pedido entregue ao celular), `entregue` (operadora confirmou) e `falhou`. O comprovante é idempotente e nunca rebaixa um pedido `entregue`.

### API para o PDV

Escuta em `0.0.0.0:<porta_http>` (padrão 8766). Autenticação por `X-Api-Token` ou `Authorization: Bearer <token>`; a comparação usa `secrets.compare_digest`.

| Método e rota | Função |
| --- | --- |
| `GET /api/health` | Estado da ponte, sem token: `ok`, `phone_online` e quantidade pendente. |
| `POST /api/sms` | Enfileira um SMS. Corpo: `{"number","venda_id","template","variaveis"}`. |
| `GET /api/sms` | Últimos 20 pedidos, sem número, texto nem envelope. |
| `GET /api/sms/<id>` | Um pedido pelo identificador, no mesmo formato reduzido. |
| `GET /api/sms/e2e` | Se a criptografia de ponta a ponta é obrigatória, se a chave do celular existe e o fingerprint. |
| `POST /api/mobile/diagnostic` | Recebe o diagnóstico do celular no pareamento (token de setup) e a chave pública. |
| `POST /api/mobile/key` | Celular já pareado publica a chave pública; blob AES-GCM com a chave do pareamento. |
| `POST /api/mobile/receipt` | Recebe o comprovante do celular (blob AES-GCM com a chave do pareamento). |

`POST /api/sms` e `GET /api/sms*` só são aceitos de `127.0.0.1`/`::1`; pedido vindo da rede recebe `403`. O `POST` também exige a assinatura `X-Gaspar-Signature` (HMAC-SHA256 de `método\ncaminho\ntimestamp\nnonce\nsha256(corpo)`, com `X-Gaspar-Timestamp` e `X-Gaspar-Nonce`), tolerância de 60 s e nonce de uso único por 10 min.

Códigos de `POST /api/sms`: `202` aceito, `400` número/mensagem/modelo inválidos, chave do celular ausente ou corpo malformado, `401` token ou assinatura ausente, inválida, expirada ou repetida, `403` chamada fora do computador, `429` limite por minuto, por dia, por destinatário ou pedido repetido, `507` fila cheia. A resposta inclui `sealed`, `destino` e `conteudo` (rótulos HMAC), sem número nem texto.

O conteúdo é sempre um modelo: `template: "venda_confirmada"` com `variaveis: {"venda": "123", "total": "19,90"}` (o total é opcional). Texto livre é recusado enquanto `only_templates` estiver ligado. O envio de teste do painel é a única exceção, e é marcado como `origem: "painel"` na auditoria.

Códigos de `POST /api/mobile/receipt`: `202` comprovante aplicado, `400` blob ausente, adulterado ou com estado inválido, `404` pedido desconhecido.

Exemplo de chamada do PDV (o mesmo cálculo está em `gaspar/sms/signing.py`):

```python
import hashlib, hmac, json, secrets, time, urllib.request

token = "SEU_TOKEN"
corpo = json.dumps({
    "number": "5511999999999",
    "template": "venda_confirmada",
    "variaveis": {"venda": "123", "total": "19,90"},
    "venda_id": "venda-123",
}).encode()
nonce, agora = secrets.token_hex(8), int(time.time())
base = "\n".join(["POST", "/api/sms", str(agora), nonce, hashlib.sha256(corpo).hexdigest()])
assinatura = hmac.new(token.encode(), base.encode(), hashlib.sha256).hexdigest()
pedido = urllib.request.Request("http://127.0.0.1:8766/api/sms", data=corpo, method="POST")
for nome, valor in {
    "Content-Type": "application/json",
    "X-Api-Token": token,
    "X-Gaspar-Timestamp": str(agora),
    "X-Gaspar-Nonce": nonce,
    "X-Gaspar-Signature": assinatura,
}.items():
    pedido.add_header(nome, valor)
print(urllib.request.urlopen(pedido).read().decode())
```

```json
{"ok": true, "id": "7f3c...", "status": "fila", "confirmed": false, "sealed": true, "destino": "3f2a...", "conteudo": "9c1b..."}
```

O PDV deve tratar `sem resposta`, `401`, `403`, `429` e `507` como "não enviado" e tentar de novo mais tarde; o `venda_id` impede duplicidade quando a nova tentativa acontece dentro de 24 horas. O diagnóstico do celular usa `POST /api/mobile/diagnostic` com `token`, `sms_ok`, `battery_ok`, `message` e `phone_public_key`; esse token é o de pareamento, não o da API, e é apagado depois do primeiro uso.

### Regras de segurança e de custo

- Número normalizado entre 10 e 15 dígitos, com `+` opcional; mensagem limitada a 480 caracteres.
- `venda_id` é idempotente por 24 horas: repetir a mesma venda devolve o pedido já existente em vez de mandar outro SMS.
- Limites padrão: 20 pedidos por minuto e 300 por dia; fila máxima de 100 pedidos.
- Por destinatário: 1 por hora e 3 por dia. O mesmo texto para o mesmo destino em 30 minutos devolve o pedido existente em vez de enviar de novo. Os limites contam pelo rótulo HMAC do número, não pelo número gravado.
- No máximo duas tentativas por pedido. Celular offline gera `falhou` com o motivo, sem repetir para sempre.
- Ao abrir, pedidos `fila` voltam para a fila; pedidos `enviando` viram `falhou` com "envio interrompido ao fechar o Gaspar", para não arriscar cobrança duplicada.
- O app Android guarda um contador de sequência (`seq`) e recusa pedido com sequência repetida; também limita a 300 SMS por dia no próprio aparelho e ignora um identificador de pedido já aceito.
- `sms_config.json` é gravado com permissão restrita (quando o sistema permite). A auditoria não guarda número nem texto; o estado guarda o envelope cifrado, que o Gaspar não abre.
- O token da API, a chave compartilhada e a chave de auditoria só existem no computador do lojista. Nenhum segredo é versionado no repositório.

### Arquivos da ponte

| Arquivo | Conteúdo |
| --- | --- |
| `sms_config.json` | Estado, porta, token da API, chave compartilhada, chave de auditoria, chave pública do celular, limites e retenção. |
| `sms_state.json` | Até 500 pedidos, com status, horários, o envelope cifrado e os rótulos HMAC; sem número nem texto. |
| `sms_audit.jsonl` | Trilha de uma linha por mudança de estado, só com metadados; retenção padrão de 90 dias. |

Todos ficam na pasta de dados do usuário (`data_dir()`), respeitando `GASPAR_HOME`. O guia do usuário e o passo a passo do celular estão em [wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html); o termo de privacidade está em [wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html).

## Canal de atualização

O Gaspar tem um canal próprio. O aplicativo consulta um único arquivo assinado,
publicado como conteúdo estático no GitHub Pages e espelhado pelo gateway. A
partir da 1.7.2 a ordem é: gateway primeiro, domínio antigo como reserva.

```text
principal  https://api.caracore.com.br/releases/gaspar/latest.json
reserva    https://gaspar.caracore.com.br/latest.json
```

Os dois endereços entregam os mesmos bytes. A assinatura é conferida em
qualquer um deles com a chave pública embutida, então a reserva não é um
caminho mais fraco: se o gateway devolver um manifesto que não confere, a
atualização não é aceita. Quando a reserva responde, o log registra
`Canal de atualizacao: respondendo pelo endereco de reserva.`; a volta ao
principal também fica registrada.

O DNS `gaspar.caracore.com.br` aponta para `chmulato.github.io`; a esteira
[`channel.yml`](../.github/workflows/channel.yml) publica o arquivo depois de
conferir a assinatura. A mesma publicação serve a página de apresentação
(`docs/index.html` e `docs/assets/`) na raiz do site, e o `latest.json` fica ao
lado dela. Não existe servidor de aplicação, banco nem chave privada na nuvem.

O gateway `api.caracore.com.br` serve o **mesmo arquivo** como espelho, em
`/releases/gaspar/latest.json`. Ele baixa o `latest.json` da release `gaspar-v*`
e entrega os bytes sem assinar de novo: a assinatura é conferida pelo aplicativo
com a chave pública embutida. O gateway não guarda a chave privada do Gaspar e
também é separado do produto CSO Transporte, que usa o mesmo host com regras
próprias. Ele guarda a resposta por até 5 minutos, por isso uma versão recém
publicada pode demorar alguns minutos para aparecer aos aplicativos.

A esteira [`canal-monitor.yml`](../.github/workflows/canal-monitor.yml) confere o
canal publicado a cada 6 horas, sem publicar nada: baixa os dois endereços,
valida a assinatura em cada um, exige bytes iguais, exige que a versão publicada
seja a da release mais nova (rascunhos e pré-releases não contam) e confere se os
pacotes do manifesto continuam no ar com o tamanho declarado. Qualquer desvio
falha a execução. O mesmo comando roda na mão:

```bash
python tools/gaspar_channel.py monitor
```

### Contrato do `latest.json`

O arquivo é um envelope com o manifesto em base64 e a assinatura Ed25519:

```json
{
  "payload": "<JSON compacto em base64>",
  "signature": "<assinatura Ed25519 em base64>",
  "key_id": "gaspar-2026-11",
  "appId": "gaspar",
  "version": "1.7.2",
  "downloadUrl": "https://github.com/.../GasparSetup-1.7.2.exe",
  "sha256": "...",
  "mandatory": false,
  "releaseNotes": "...",
  "assets": { "windows-setup": { "url": "...", "sha256": "...", "size": 0 } }
}
```

Os campos fora do `payload` são espelhos para leitura humana. O aplicativo
**ignora todos eles** e usa somente o que está dentro do payload assinado:

| Campo | Regra |
| --- | --- |
| `appId` | Precisa ser `gaspar`. |
| `version` | Versão publicada, comparada em partes numéricas. |
| `channel` | Precisa ser `stable`. |
| `mandatory` | Verdadeiro deixa a atualização obrigatória. |
| `min_supported` | Quem estiver abaixo também recebe a atualização como obrigatória. |
| `published_at` | Data de publicação da release. |
| `notes_url` | Página de novidades. |
| `releaseNotes` | Texto da release. |
| `assets` | Pacotes por plataforma, com `url`, `sha256` e `size`. |

O aplicativo calcula `obrigatória = mandatory OR versão_local < min_supported`.
Não existe variante separada do manifesto para atualização obrigatória.

Chaves de asset: `windows-setup` (obrigatório, nome `GasparSetup-*.exe`) e
`linux-deb` (opcional, nome `gaspar_*_amd64.deb`). A URL é montada como
`https://github.com/{repo}/releases/download/{tag}/{asset}`.

### Confiança, assinatura e limites

- A chave privada Ed25519 fica no HD removível do responsável e é lida apenas de
  `GASPAR_RELEASE_SIGNING_KEY` (PEM ou PKCS#8 em base64). Ela nunca é versionada,
  impressa ou enviada.
- A chave pública fica em `assets/gaspar-update-public.pem`, entra no repositório
  e no instalador. O aplicativo não liga o canal quando ela está ausente.
- A assinatura é conferida **antes** de interpretar o payload; qualquer campo
  fora do payload é ignorado.
- Só HTTPS; HTTP é aceito apenas em `127.0.0.1`/`localhost` para testes. O
  manifesto tem limite de 64 KB e o instalador, 256 MB.
- No Windows, o pacote precisa terminar em `.exe`; o SHA-256 assinado é
  conferido durante o download e o arquivo parcial é apagado em caso de erro.

### Fluxo no aplicativo

1. `updates.Vigia` consulta o canal 25–60 s depois de abrir e a cada 6 h
   (variação de ±15 min). Se a última consulta tem menos de 30 min, espera.
2. A faixa **Atualização** aparece no painel e o item correspondente no menu da
   bandeja. A notificação da bandeja é emitida uma vez por versão.
3. **Depois** grava `deferred_version` e esconde a faixa; ela não volta sozinha,
   mas continua acessível pela bandeja.
4. **Pular** grava `skipped_version` e remove o item da bandeja.
5. **Atualizar agora** (Windows) baixa para `data_dir()/updates`, confere o
   SHA-256, grava `pending_version` e dispara um PowerShell oculto que espera o
   PID atual terminar, executa o instalador com
   `/SILENT /SUPPRESSMSGBOXES /NORESTART`, grava `update-result.txt` e reabre o
   app com `--minimized`. O instalador Inno é por usuário e não tem entrada de
   `[Run]` para o modo silencioso: quem reabre é o roteiro do updater, para não
   abrir duas instâncias do Gaspar.
6. Na abertura seguinte, o app lê `update-result.txt`, registra sucesso ou falha
   e limpa `pending_version`. No Linux, o botão abre a página de download.

O estado fica em `data_dir()/update.json`:

| Campo | Uso |
| --- | --- |
| `last_check` | Última consulta bem-sucedida (epoch). |
| `skipped_version` | Versão que o usuário não quer mais ver. |
| `deferred_version` | Versão que o usuário adiou. |
| `notified_version` | Versão já notificada na bandeja. |
| `pending_version` | Versão cuja instalação foi iniciada. |

### Ferramenta e esteira

| Comando | Efeito |
| --- | --- |
| `python tools/gaspar_channel.py init-key --key <caminho>` | Gera o par; recusa caminho dentro do repositório. |
| `python tools/gaspar_channel.py sign --tag gaspar-vX.Y.Z` | Gera `dist/channel/latest.json` local. |
| `python tools/gaspar_channel.py sign --tag ... --publish` | Envia o manifesto à release, dispara `channel.yml`, acompanha e confere a URL pública. |
| `python tools/gaspar_channel.py check --expect X.Y.Z` | Consulta o canal publicado e valida a assinatura. |
| `python tools/gaspar_channel.py prova --tag gaspar-vX.Y.Z` | Repete o aceite da release no canal oficial e no espelho, baixa o instalador e confere o SHA-256. |
| `python tools/gaspar_channel.py verify --file latest.json` | Valida um arquivo local (usado pela esteira). |

A configuração do canal fica em `release/channel.json` (repositório, prefixo de
etiqueta, `key_id`, `min_supported`, `notes_url`, endereço do canal, endereço do
espelho e padrões de asset). A ferramenta importa `gaspar.updates`, então o
manifesto é provado com a mesma verificação que o aplicativo usa.

### Publicar uma versão

Uma vez só, com o HD removível conectado, gere o par de chaves:

```bash
python tools/gaspar_channel.py init-key --key E:/gaspar/gaspar-signing.pem
```

A chave privada fica fora do repositório e não pode ser recuperada: sem ela não
é possível assinar versões novas. A chave pública vai para
`assets/gaspar-update-public.pem`, entra no instalador e é versionada. Enquanto
ela não existir, o aplicativo mantém o canal desligado.

Em cada versão:

1. Suba a versão em `gaspar/__init__.py` e gere os pacotes. A esteira recusa a
   etiqueta `gaspar-vX.Y.Z` que não bata com `gaspar.__version__`.
2. Crie o rascunho da release com o `GasparSetup-X.Y.Z.exe`, o `.deb` e o texto
   das novidades. Rascunho e pré-release são recusados pela ferramenta e pela
   esteira até serem publicados.
3. **Publique a release.**
4. Com o HD removível conectado, **assine e publique o manifesto** no
   PowerShell:

   ```powershell
   $env:GASPAR_RELEASE_SIGNING_KEY = Get-Content E:\gaspar\gaspar-signing.pem -Raw
   python tools/gaspar_channel.py sign --tag gaspar-vX.Y.Z --publish
   Remove-Item Env:GASPAR_RELEASE_SIGNING_KEY
   ```

   O comando envia o `latest.json` à release, dispara a esteira do Pages,
   acompanha o resultado e confere o endereço público.
5. **Rode a prova dupla:**

   ```bash
   python tools/gaspar_channel.py prova --tag gaspar-vX.Y.Z --tentativas 36
   ```

   As tentativas esperam até 6 minutos pelo cache do Pages e do gateway (o
   gateway guarda a resposta por 5 min). A prova só fecha quando:

   - o canal oficial responde a versão pedida e a assinatura confere;
   - o espelho entrega **os mesmos bytes** do canal oficial;
   - o payload assinado confere com a release (versão, `mandatory`,
     `min_supported`, notas, URLs e SHA-256 dos dois pacotes);
   - cada versão anterior publicada recebe o aviso com a obrigatoriedade certa
     (abaixo de `min_supported` a atualização é obrigatória);
   - a versão atual não recebe aviso;
   - o instalador baixado do endereço do manifesto tem o SHA-256 assinado;
   - um manifesto com a versão trocada sem assinar de novo é recusado.

Uma linha `mandatory: true` no texto da release marca a atualização como
obrigatória; versões abaixo de `min_supported` também. Depois de publicar,
ajuste `min_supported` em `release/channel.json`: o valor entra no próximo
manifesto assinado.

Quem está na 1.7.0 instala a primeira versão com atualizador **uma vez, à mão**.
A partir dela o aviso passa a funcionar sozinho. O passo a passo para quem usa o
Gaspar está em [atualizacao.html](../docs/atualizacao.html).

### Repositório misto

O repositório publica o Gaspar (tags `gaspar-v*`) e o aplicativo Android (tags
`android-v*`). O canal não usa `/releases/latest`: ele aponta para o
`latest.json` da release indicada, e a ferramenta e a esteira recusam etiqueta
fora de `gaspar-v*`, para que uma release Android não vire "a mais recente" do
canal.

## Testes

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python tests/smoke_test.py
```

Os 59 testes unitários de `tests/test_sms.py` usam apenas biblioteca padrão (mais `cryptography`) e não abrem porta fixa nem acessam a internet. Eles cobrem:

- Configuração, geração e persistência dos segredos, token de setup de uso único e validade de 15 minutos.
- Derivação de chave quando o segredo tem menos de 32 bytes.
- Cifra e decifra no formato do app Android, incluindo detecção de adulteração.
- Envelope de ponta a ponta: ida e volta, AAD amarrado ao pedido, chave efêmera por mensagem, chave pública inválida e rótulos HMAC estáveis.
- Enquadramento TCP, montagem do comando e leitura do anúncio de descoberta.
- Normalização de número e de mensagem, com recusa de entradas inválidas.
- Persistência, deduplicação por `venda_id` e restauração da fila; pedido antigo é selado antes de sair.
- Envio com sucesso, repetição com celular offline, falha definitiva, limite por minuto e fila cheia.
- Assinatura HMAC: ausência, chave errada, relógio fora da janela e nonce repetido.
- Limites por destinatário, repetição de conteúdo, modelo de mensagem e envio manual do painel.
- API local: saúde, autenticação, aceite, consulta por id, pedido inexistente, `403` fora do computador, diagnóstico de uso único e rota da chave pública.
- Comprovante: aceite e falha pelo celular, transição `enviado` → `entregue`, comprovante adulterado, pedido desconhecido e recusa sem token da API.
- Privacidade: `sms_state.json` e `sms_audit.jsonl` não contêm número nem texto; a auditoria recusa campos de conteúdo; expurgo respeita a retenção; o expurgo manual apaga os dois.
- Android: o manifesto mantém `SendSmsActivity` fechada e a permissão interna como `signature`.

Os 27 testes de `tests/test_updates.py` também usam apenas biblioteca padrão
(mais `cryptography`) e não acessam a internet nem usam chave real. Eles cobrem:

- Envelope assinado aceito; adulteração, outro `appId` e outro canal recusados.
- Campos espelho fora do payload ignorados.
- Comparação de versões, prefixo `v`, pré-release e versão abaixo do mínimo.
- Escolha do instalador por plataforma e recusa de manifesto sem pacote.
- Download local com SHA-256 correto e incorreto (arquivo parcial apagado).
- Persistência de estado e leitura do marcador de instalação.
- Ferramenta: payload com os dois pacotes, divergência entre `digest` e
  `SHA256SUMS.txt`, rascunho, pré-release, etiqueta de outro produto e release
  sem instalador recusados; o manifesto gerado passa pela verificação do app.
- Roteiro PowerShell: espera o PID, argumentos silenciosos, marcador de
  resultado e escape de apóstrofo no caminho (sintaxe validada no PowerShell).

Os 12 testes de `tests/test_channel.py` provam a rotina de release sem rede e
sem chave real: espelho com bytes diferentes recusado, manifesto de outra
release recusado, `key_id` trocado recusado, canal atrasado sinalizado para
nova tentativa, versão adulterada recusada, regra de obrigatoriedade por
`min_supported` e conversão das etiquetas (`gaspar-v1.7.1`, `v1.6.0`;
`android-v1.3` é ignorada).

Os 2 testes de `tests/test_isolamento.py` falham se um domínio de pagamento ou
de nota fiscal (`api.mercadopago.com`, `api.plugnotas.com.br` e o sandbox)
aparecer na lista do BlackBox ou no código do pacote.

O teste de fumaça usa uma pasta temporária via `GASPAR_HOME`, não altera o `hosts` real e cobre:

- Persistência de configuração (incluindo modo discreto e pausa em tela cheia).
- Aplicação, idempotência e remoção do bloco de telemetria em um arquivo temporário.
- Leitura de ausência e detecção de tela cheia.
- Criação do painel e do overlay reais.
- No Windows: chave de cor `#ff00ff`, opacidade 82%, clareamento para 12% perto do cursor, `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_NOACTIVATE`, click-through e z-order abaixo do painel.
- Trajeto apenas entre cantos vizinhos, sem cruzar o centro.
- Sumiço e retorno durante tela cheia simulada.
- Abertura da janela **Celular / SMS** com a ponte desligada (sem abrir porta nem acionar o firewall).
- Criação do `cycle_log.txt`.

Em Linux, a parte gráfica é pulada quando não há `DISPLAY` nem `WAYLAND_DISPLAY`.

## Solução de problemas

**`pip` não é reconhecido no Windows**

Use `python -m pip install -r requirements.txt` ou adicione a pasta `Scripts` do Python ao `PATH`.

**O mascote aparece com um quadrado de fundo no Linux**

A sessão não está em X11/XWayland, ou faltam `libX11`/`libXext`. Instale as bibliotecas e entre numa sessão X11. Em Wayland puro, o recorte do X11 não funciona.

**O mouse se mexe enquanto trabalho**

Confirme que **Agir somente quando eu estiver ausente** está marcado. Em sistemas sem detecção de ausência, o app avisa no log e segue apenas o intervalo; aumente o intervalo ou desmarque **Movimentar o mouse**.

**O mascote cobre o painel**

Ele deve ficar atrás do painel enquanto a janela de configuração está aberta. Se não ficar, feche e reabra o painel; o z-order é reaplicado a cada 500 ms.

**O BlackBox não abre pelo ícone da bandeja**

Gere o build completo (Gaspar e BlackBox). No Windows, o instalador inclui os dois; no Linux, o `.deb` e o AppImage incluem os dois. O atalho **Gaspar BlackBox** do menu iniciar continua disponível.

**Antivírus ou SmartScreen bloqueia o `.exe`**

O executável não é assinado. Adicione uma exceção somente se você confia na origem e compilou a partir deste repositório.

**Nada é registrado no log**

Verifique a pasta de dados do usuário e a permissão de escrita. Em testes, defina `GASPAR_HOME` para uma pasta temporária.

**O Windows pede permissão de firewall ao ligar a ponte de SMS**

É esperado: a API precisa aceitar conexões na rede local para o PDV e o celular. Autorize somente em redes privadas. Se a porta 8766 estiver ocupada, o Gaspar avisa no registro da ponte; troque a porta na janela **Celular / SMS**.

**O celular não aparece em Procurar celular**

Confirme que o celular e o computador estão na mesma rede Wi-Fi, que o aplicativo Android está aberto e que a rede não isola os dispositivos (redes de visitante costumam bloquear). O pareamento por QR funciona mesmo sem a descoberta. Mais casos em [wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html).

## Migração da versão anterior

| Arquivo antigo | Novo local |
| --- | --- |
| `mascote.py` | `gaspar/app.py` + `run.py` |
| `mascote_blackbox.py` | `gaspar/blackbox.py` + `run_blackbox.py` |
| `block-telemetry-hosts.py` | `gaspar/telemetry_hosts.py` |
| `mascote_exe.py` | `packaging/windows/build_windows.py` |
| `mascote.spec` | `packaging/windows/gaspar.spec` |
| `mascote_blackbox.spec` | `packaging/windows/gaspar_blackbox.spec` |
| `mascote.gif` / `mascote.ico` / `boneco.ico` | `assets/gaspar_flutuando.gif` / `assets/gaspar.ico` / `assets/gaspar.png` |
| `README.txt` | `README.md` |
| `PIP_CONFIGURACAO.txt` | seção de solução de problemas do guia técnico |
| `BLACKBOX_AMBIENTE_DESENVOLVIMENTO.txt` | [wiki.caracore.com.br/gaspar/blackbox.html](https://wiki.caracore.com.br/gaspar/blackbox.html) |

## Regenerar os ativos

Os ativos oficiais podem ser regenerados a partir da arte original em fundo magenta:

```bash
python tools/make_assets.py caminho/para/gaspar_original.png
```

O script remove o magenta, recorta o mascote, suaviza a borda, desconta a franja magenta e grava PNG, ICO e GIF em `assets/`.

## Estado de validação desta versão

- Testes automáticos: **105 testes** — 59 da ponte de SMS, 27 do canal, 12 da rotina de release, 2 de isolamento e 5 do teste de fumaça —, aprovados na árvore local; a esteira `gaspar.yml` executa os 100 testes unitários no Linux e no Windows e o teste de fumaça no Linux.
- Canal de atualização: **no ar**. O DNS `gaspar.caracore.com.br` aponta para o Pages, e o `latest.json` (2.882 bytes) foi assinado com a chave `gaspar-2026-11` e publicado na [Release 1.7.1](https://github.com/chmulato/caracore-mascote/releases/tag/gaspar-v1.7.1). O gateway `api.caracore.com.br/releases/gaspar/latest.json` entrega os mesmos bytes. O comando `prova --tag gaspar-v1.7.1` repetiu o aceite nos dois endereços, conferiu o SHA-256 do instalador baixado do manifesto e recusou um manifesto adulterado. A chave privada fica só no HD removível do responsável; a pública está versionada em `assets/gaspar-update-public.pem` e dentro dos dois pacotes. A 1.7.2 (na árvore, ainda não publicada) inverte a ordem: consulta o gateway primeiro e deixa o domínio antigo como reserva.
- Atualização real de ponta a ponta (baixar, instalar em silêncio e reabrir): **não executada**. O roteiro PowerShell foi validado por análise sintática, não por uma atualização disparada pelo app. O ciclo 1.7.0 → 1.7.1 foi medido em 12/11/2026 como reinstalação manual por cima: versão final 1.7.1, preferências e token preservados, canal consultado no primeiro minuto e desinstalação limpa. O caminho automático 1.7.1 → N depende da primeira versão publicada depois da 1.7.1.
- Janela **Celular / SMS**: validada no teste de fumaça com a ponte desligada; o pareamento real depende de um celular Android.
- Botão **Tirar o Gaspar da tela**: validado no teste de fumaça; o mascote some, o botão vira **Trazer o Gaspar de volta** e a simulação e a ponte continuam ativas.
- Envio real de SMS: **não executado** nesta máquina, porque depende de um celular Android pareado e de um chip com crédito. O protocolo foi validado contra o código do app Android em teste automatizado (mesma derivação de chave e mesmo formato de cifra).
- Pacotes 1.7.1: gerados pela esteira nos dois sistemas, com `SHA256SUMS.txt` conferido e publicado na Release 1.7.1 — instalador 31 MB, `.deb` 41 MB e AppImage 30 MB.
- A instalação dos pacotes 1.7.1 em Debian 12 não foi medida nesta versão; a última instalação medida (Debian 12, `.exe` empacotado e AppImage) foi a da 1.6.0, com a mesma receita de build (Inno Setup 6 na máquina de build).
- Aplicativo Android 1.2: APK e AAB **assinados** gerados pela esteira e publicados na [Release Android 1.2](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.2); o APK não foi instalado em celular nesta máquina. O código de `android/` já é o 1.3 e tem um rascunho de release (`android-v1.3`), ainda não publicado. Por isso o SMS no Gaspar 1.7.1 depende de uma versão do celular que ainda não foi distribuída.
- Nenhum APK, keystore ou senha é versionado.
