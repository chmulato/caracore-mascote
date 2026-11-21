# Guia técnico do Gaspar

Documentação para quem mantém, compila ou audita o Gaspar. O guia do usuário está no [README](../README.md).

- Branch oficial: **master**
- Versão: **1.7.4** (publicada)
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
│   ├── test_app.py                # 89 testes do painel (janela real escondida)
│   ├── test_core.py               # 45 testes do núcleo sem tela
│   ├── test_e2e_sms.py            # 6 testes de ponta a ponta da ponte
│   ├── test_e2e_update.py         # 7 testes de ponta a ponta do canal
│   ├── test_engine.py             # 20 testes do motor de presença
│   ├── test_isolamento.py         # 2 testes de isolamento das integrações
│   ├── test_channel.py            # 12 testes da rotina de release
│   ├── test_phone.py              # 15 testes de rede, descoberta e QR
│   ├── test_sms.py                # 59 testes da ponte
│   ├── test_updates.py            # 43 testes do canal (atualizador e ferramenta)
│   └── test_updates_extra.py      # 29 testes de lacunas do canal
├── tools/
│   ├── gaspar_channel.py          # init-key, sign, prova, check, monitor e verify
│   └── make_assets.py
├── .github/workflows/
│   ├── android.yml
│   ├── canal-monitor.yml
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
- `dist/installer/GasparSetup-1.7.4.exe` (quando o Inno Setup está instalado)

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
- `dist/linux/gaspar_1.7.4_<arch>.deb`
- `dist/linux/Gaspar-1.7.4-<arch>.AppImage`

Instalação do `.deb`:

```bash
sudo apt install ./dist/linux/gaspar_1.7.4_amd64.deb
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
chmod +x dist/linux/Gaspar-1.7.4-amd64.AppImage
./dist/linux/Gaspar-1.7.4-amd64.AppImage
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
- O aplicativo publicado (1.7) envia a chave pública e recebe a licença digitada no painel (ou aplicada pelo QR de pareamento), sem ler SMS. O 1.2 não envia a chave pública; por isso o Gaspar 1.7.1 ou mais novo, com `e2e_required` no padrão, recusa o envio até o celular ser atualizado (o indicado hoje é o 1.7). Quem continua no Gaspar 1.7.0 fica com o aplicativo 1.2.
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

### Convivência com o motor 2.0 (a porta 49998)

Gravado em 2026-11-21 (Onda B6-A). A ponte da 1.7 e o motorista `android_lan` do motor 2.0 falam com o mesmo celular, pelo mesmo TCP na porta 49998 — o celular é o servidor e só existe um. Deixar os dois ligados ao mesmo tempo é colisão no aparelho, não no computador. A regra decidida pelo dono:

> Se o motor 2.0 (`messaging.enabled = True`) estiver ativo com o motorista `android_lan`, a ponte legada 1.7 (`sms.enabled`) cede a vez e desativa o acesso à porta 49998 automaticamente, para evitar colisão no mesmo celular. Quando o motor 2.0 estiver desligado (`enabled = False`), a 1.7 opera normalmente como hoje.

Onde isso vive no código:

- **A decisão** é uma função pura, sem Tk e sem soquete: `gaspar/messaging/convivencia.py`. `origens_com_celular(config)` responde quais origens escolheram `android_lan` (ela olha a *escolha*, independente do motor estar ligado), `motor_ligado(config)` lê o `enabled` e `celular_reservado(config)` junta os dois. `motivo_celular_reservado(config)` devolve a frase que vai para a tela do lojista, com as origens e o número da porta.
- **A recusa de abrir a 1.7** está no começo de `_start_sms_services()` em `gaspar/app.py`: havendo reserva, a ponte não sobe, o motivo entra no log do painel e na linha de estado da aba Celular (`sms_api_var`), e o token da 1.7 continua visível para quem precisa dele. O botão «Ligar ponte de SMS» (`_on_sms_enabled`) também respeita a reserva: ele salva a vontade do lojista e escreve o aviso em vez de mandar nada ao celular.
- **O envio de teste do painel obedece a mesma regra** (`_on_test_send`), desde 21/11/2026. Antes dela o botão enfileirava no `_SmsBridge` parado: a janela lia «Teste de SMS enfileirado» enquanto nada saía, e o pedido ficava na gaveta à espera de a barra ser desligada — hora em que sairia sozinho, sem que ninguém tivesse voltado a pedir. Agora a reserva é consultada antes do `enqueue`, e o lojista recebe o motivo, uma linha no registro de eventos (com a frase do `motivo_celular_reservado`) e o caminho na tela — desligar o quadro **Mensagens pelo computador (barra 2.0)** da mesma aba. O botão continua sendo da 1.7: nada dele toca a API `/v2/messages`. **Estado deste texto:** a regra está escrita e medida na árvore local de 21/11/2026, ainda não versionada — na `master` `e314969` o teste continua entrando na fila sem aviso (fila de polimento da Fase de Validação Real, item D-1).
- **Quem liga depois de a 1.7 já estar de pé** também é coberto: `_start_messaging()` desliga a ponte 1.7 que já estava rodando e registra o mesmo motivo na tela.

O que a regra **não** faz, e o que ela custa, escrito para ninguém descobrir tarde:

- **Ceder não se desfaz sozinho.** Se o lojista desligar o motor 2.0, a 1.7 não volta a usar o celular sozinha nesta execução — ela volta quando o Gaspar reiniciar ou quando o lojista ligar a ponte na aba Celular. Quem cedeu precisa ser religado de propósito.
- **Bloco de ajustes não reserva nada.** Ter um `transport_settings.android_lan` no arquivo sem nenhuma origem apontando para `android_lan` deixa o celular livre para a 1.7. Só a escolha por origem conta.
- **A reserva olha a escolha, não a saúde do motorista.** Um balcão que ligar o motor com `android_lan` sem levar o pareamento para `segredo_sealed` fica com as duas pontas desligadas: a 1.7 cede o celular por causa da escolha, e o 2.0 recusa cada pedido — `health()` mede `disponivel: false` com o motivo «celular sem segredo de pareamento», e com a chave faltando «celular sem chave de criptografia; pareie o celular de novo». O lojista vê na aba Celular quem ficou com o aparelho e, desde a **B6-6** (21/11/2026), também o motivo que o próprio motorista deu: a linha fecha com «ainda nao esta pronto: celular sem segredo de pareamento». Quem prepara a máquina pela tela só digita a senha no campo **Segredo do pareamento**; quem vai por linha de comando ainda precisa selá-la no arquivo (receita em «Segredo só selado» abaixo).
- **O segredo de pareamento não migra sozinho.** `android_lan` não lê `sms_config.json`: quem já tinha a 1.7 pareada precisa levar a mesma chave para o `messaging.json`, selada pela chave da fila. Deixar a herança automática de fora foi escolha desta onda, para não importar em segredo um arquivo que o lojista pode querer desligar.

A prova são os 12 casos de `tests/test_messaging_convivencia.py` (motor desligado não reserva; origem a origem reserva e nomeia a origem na frase; as duas reservando aparecem as duas; `smtp_email` e `loopback` não reservam; grafia errada não reserva; um `SimpleNamespace` torto não derruba a consulta; a consulta não muta a configuração) mais os casos de painel em `BarraMensagens20Tests` (`tests/test_app.py`), que medem a árvore real do Tk: com reserva a ponte 1.7 fica com `started == 0`, `sms_server` é `None`, a linha de estado traz «cede a porta 49998» e o token continua lá. Do lado do balcão, `CelularSmsTests` fecha as duas metades do botão de teste — com o celular cedido o `enqueue` da 1.7 não é chamado e o aviso aponta o quadro onde desligar a barra; com o canal escolhido sendo a caixa de e-mail, o teste passa pelo `enqueue` uma vez, com `manual=True`, como sempre passou — estes dois casos são da árvore local de 21/11/2026, ainda não versionada.

## Motor de mensageria 2.0

A Fase Alpha do Gaspar 2.0 está no repositório como `gaspar/messaging/`: uma fila SQLite única em que cada pedido leva a `origem` (`PDV` ou `HUB`), com credenciais, cotas e trilha de eventos separados por origem, API local assinada em `127.0.0.1:8767` e a interface `SmsTransportDriver`, que devolve `aceito`, `recusado`, `incerto` ou `indisponivel`. O motor ainda não está ligado ao painel: `messaging.json` nasce com `enabled: false` e nenhum outro módulo do mascote importa o pacote. O que o lojista usa continua sendo a ponte de SMS da 1.7. **Corrigido em 21/11/2026 (Onda B6-A):** o `gaspar/app.py` passou a importar o pacote (dentro do mesmo `try` que protege a ponte de SMS, então pacote ausente ou quebrado só desliga a peça) e o `messaging.json` passou a escolher o motorista de cada origem. A frase continua valendo no que importa para o balcão: `enabled: false` é o padrão de fábrica, com o motor desligado nada de porta abre e nada de arquivo de estado nasce, e o que o lojista usa hoje continua sendo a ponte da 1.7. O detalhe do ligamento está em «Ligamento por arquivo e convivência com a 1.7» abaixo.

A auditoria da Fase Alpha (PR #6) registrou seis requisitos obrigatórios para abrir a Fase Beta. Eles valem como item de partida, e a coluna da prova é o que fecha cada um. Gravado em 2026-11-20.

**Ondas B1 e B2, gravado em 2026-11-20.** D1 a D5 estão cumpridos nesta onda, e D6 está cumprido na `master` (PR #9, mesclado). As células da coluna da prova dizem o que foi medido, não o que se pretende medir. Vermelho antes do código: os testes desta onda rodados sobre a `master` sem as mudanças fecharam com 89 testes, 4 falhas e 5 erros. Verde na árvore medida: 465 testes OK (1 pulo, o caso de modo de arquivo que o Windows não executa) e cobertura 81% contra o piso de 70% — `store.py` 97%, `service.py` 96%, `config.py` 91%, `local_api.py` 90%, `vault.py` 84%. Correção de registro na linha D1: a gravação citava `find_inbound`, função que não existe no motor; os buracos reais eram `mark`, `resolve_uncertain` e `get_inbound`.

| # | Requisito | Onde | Prova de que foi feito |
| --- | --- | --- | --- |
| D1 | Ler ou mutar pedido e resposta pelo `id` também filtra por `origem`, para o isolamento PDV/HUB não depender só da camada de API. | `gaspar/messaging/store.py`: `mark`, `resolve_uncertain`, `get_inbound` e o `_raw_message` que os três usam; chamadores ajustados em `dispatcher.py` e `local_api.py` | **Cumprido em 2026-11-20 (Onda B2).** Cinco casos: o `id` de um pedido do PDV apresentado pelo HUB não muda a linha nem escreve evento, conferir dúvida do vizinho cai com `UnknownMessage`, resposta já entregue a um não aparece para o outro e a contagem por minuto separa as duas origens. |
| D2 | `/v2/health` deixa de responder sem credencial e mostra apenas o motorista da origem que pediu. | `gaspar/messaging/local_api.py` e `TransportRegistry.health_for` | **Cumprido em 2026-11-20 (Onda B2).** Pergunta sem credencial cai com `401`; autenticada, a resposta traz a própria `origem` e só o meio dela. `test_saude_de_um_nao_checa_o_meio_do_vizinho` conta 0 chamadas ao motorista do vizinho, e a sonda por origem reusa o cache da sonda geral. |
| D3 | Cota por janela móvel de 60 segundos ao lado da cota diária, que hoje vira à meia-noite local do balcão. | `gaspar/messaging/store.py`: `minute_count` ao lado de `day_count`; `per_minute_limit_per_origin` em `config.py`, cobrado em `local_api.py` | **Cumprido em 2026-11-20 (Onda B2).** Padrão de 20 pedidos por minuto por origem, teto nunca acima da cota do dia, cobrado antes da cota diária. `test_cota_por_minuto_e_por_origem` gasta o limite em segundos, leva `429` e deixa o vizinho livre; `test_a_janela_de_sesenta_segundos_deixa_o_pedido_antigo_para_tras` conta 3 dentro da janela e 0 no segundo 61. |
| D4 | O rótulo que casa a resposta do cliente passa a ser HMAC-SHA256 truncado, em vez de `SHA-256(domínio + valor + chave)`. | `gaspar/messaging/vault.py`: `tag` com subchave derivada (`_derive`) e domínio `tag-v2` | **Cumprido em 2026-11-20 (Onda B2).** Vetores fixos numa chave de teste: `zl1QeMSKjd1ge1w0` (destino), `18SVsje9JhiJpQHu` (`id_externo`), `RWzYueNEiHLsWnDl` (vazio); o mesmo número nunca dá o mesmo rótulo em domínios diferentes, e uma chave de fora não reproduz o rótulo de dentro. Medido na `master`: o mesmo par chave/número dava `IxJiBM0xFa8CPf-D`, e a conta usava a própria subchave que cifra o conteúdo. A troca muda o rótulo, como previa esta linha, e vale porque nenhuma fila desse motor chegou a existir num balcão. |
| D5 | A chave da fila nasce com ACL restrita ao usuário no Windows, e a falha de restringir aparece no estado em vez de sumir dentro do `chmod` que o sistema ignora. | `gaspar/messaging/vault.py`: `load_or_create`, `restrict_to_owner` e `Vault.permissoes_fechadas`, reportado por `MessagingService.status()` | **Cumprido em 2026-11-20 (Onda B2).** Num arquivo de chave criado em pasta temporária o Windows dava 3 acessos herdados (sistema, administradores e direitos do proprietário) e passa a dar 1, o do dono da conta. O `icacls` só fecha com o SID escrito `*S-1-5-…:F`: com o SID puro ele sai 1332 e nada muda. Na criação, recusa significa chave que não nasce e nenhum arquivo que sobra; numa chave que já estava lá o reaperto é brando, e a recusa aparece no estado como `chave_restrita_ao_dono: false`. Oito casos em `PermissoesDaChaveTeste`: os dois que leem a ACL real só rodam no Windows, e no lugar contrário entra o caso do modo 0600. |
| D6 | Os submódulos de `gaspar.messaging` entram na lista fixa dos dois specs de empacotamento e a presença deles é provada no pacote. | `packaging/windows/gaspar.spec`, `packaging/linux/gaspar.spec`, `packaging/verifica_pacote.py`, `tests/test_packaging_manifest.py` | **Cumprido em 20/11/2026 (Onda B1).** Medido no artefato, não na árvore: o `gaspar.exe` gerado na `master` sem a lista tinha 629 módulos congelados, 26 do Gaspar e **0** dos 13 da mensageria. Com a lista, são 646 módulos, 39 do Gaspar e **13/13**, sem que nenhum dos 15 da ponte de SMS tenha sumido (diferença conferida conjunto por conjunto: 0 perdidos). Os quatro módulos a mais que não são da mensageria são `sqlite3`, que o pacote da 1.7 não precisava congelar e a fila do 2.0 passa a precisar. A mesma varredura virou passo dos dois jobs de pacote (`Conferir os módulos da mensageria no pacote (D6)`) e o `tests/test_packaging_manifest.py` compara a lista dos specs com o conteúdo de `gaspar/messaging/` a cada Portão. **Acrescido em 20/11/2026 (Onda B3):** `gaspar.messaging.transports.smtp_email` entrou nos dois specs e a lista foi de 13 para 14 módulos; a presença dentro do executável continua provada pelo passo que varre o artefato, não pela lista. **Acrescido em 20/11/2026 (Onda B4):** `gaspar.messaging.transports.android_lan` entrou nos dois specs e a lista foi de 14 para 15 módulos — o guardão mediu os 15 contra os 15 arquivos de `gaspar/messaging/` no Portão. **Acrescido em 21/11/2026 (Onda B6-A):** `gaspar.messaging.convivencia` e `gaspar.messaging.transports.factory` entraram nos dois specs, que vão de 15 para 17 módulos listados contra os 17 arquivos de `gaspar/messaging/`. Esta onda é também a primeira em que a mensageria entra no grafo de importes do `gaspar/app.py` (dentro do `try`), então o PyInstaller passaria a congelá-la sozinho — a lista fixa continua, e a varredura do artefato é que prova a presença. |

**Nota da Onda B1 sobre o mecanismo do D6.** O texto original desta tabela dizia que o `try` de `gaspar/app.py` escondia o módulo do PyInstaller. Não esconde: a análise estática do PyInstaller enxerga `import` até dentro de função, e a prova está no próprio pacote da 1.7.4 — `gaspar.sms.audit`, `.e2e`, `.signing` e `.templates` saem no executável sem estar listados nos specs. O que deixa a mensageria de fora é outra coisa: hoje nenhum arquivo de `gaspar/` importa `gaspar/messaging/`, então ela não está no grafo e só entra por lista explícita. Quando a barreira for ligada no painel, ela deve entrar pelo mesmo tipo de `try` que hoje protege a ponte de SMS — e aí, se faltar módulo no pacote, o Gaspar desliga a peça em vez de reclamar na tela do lojista. Daí as duas camadas: lista fixa nos specs e varredura do arquivo gerado.

O que falta para a Fase Beta existir é o que a RFC aprovou e ainda não foi escrito: o motorista `usb_modem` (modem USB), o ligamento no painel e o app Android 2.0. Os outros dois meios já estão escritos: a ponte de e-mail (`smtp_email`), na Onda B3, e o canal local (`android_lan`), na Onda B4 — os dois descritos abaixo, nenhum dos dois ainda no painel nem escolhível em `messaging.json`. **Corrigido em 20/11/2026 (Onda B5):** dos três itens desta frase, o app Android 2.0 deixou de faltar — ele está escrito na árvore desta branch (o `android/` sobe para `versionCode 9` / `versionName '2.0'`, Java 8 puro, zero Play Services/Firebase, com a ponte de e-mail no aparelho, a chave por origem e a tela do lojista), com gate local verde (build, 109 testes unitários do app, lint sem erros) e a tela provada em emulador Android 13. O que **continua** faltando são os outros dois: o `usb_modem` e o ligamento no painel. E nada disso está publicado: o pacote no ar segue o 1.7 (código 8), a 2.0 não tem etiqueta nem release, e `messaging.json` nasce `enabled: false` como antes. O relato do que foi medido no aparelho está em [android/STATUS_ATUAL.md](../android/STATUS_ATUAL.md).

**Corrigido em 21/11/2026 (Onda B6-A):** desta frase continua de pé só o `usb_modem` (ainda sem motorista). O que mudou: os dois meios escritos **já são escolhíveis no `messaging.json`** — `transports` por origem e `transport_settings` por motorista, montados pela fábrica nova — e o ligamento entre o arquivo e o aplicativo existe (`gaspar/app.py` lê a configuração, liga o motor quando o arquivo manda e deixa a ponte 1.7 de fora quando o celular fica com o 2.0). Faltava o lojista fazer isso sem editar arquivo: **cumprido no mesmo dia pela Onda B6-6** (aba Celular / SMS). A descrição do caminho por arquivo está em «Ligamento por arquivo (`messaging.json`) — Onda B6-A» e a da tela em «A tela do lojista — Onda B6-6».

### Ponte de e-mail (`smtp_email`)

Gravado em 2026-11-20 (Onda B3). `gaspar/messaging/transports/smtp_email.py` traz o `EmailBridgeDriver`: em vez de contratar um gateway de operadora, o computador da loja escreve o pedido na caixa postal do próprio balcão e o celular, lendo a mesma caixa, dispara pelo chip — inclusive no 4G, fora do Wi-Fi da loja. A caixa postal é a fila.

Do lado do computador:

- **Escrever** é SMTP (`ssl` na 465, `starttls` ou `plano`), com a Senha de App sempre selada pelo `Vault` do motor. Nada de senha mestra em texto claro: `EmailSettings` só conhece `password_sealed` e `bridge_key_sealed`, e o `to_dict()` grava os dois já selados — quem escrever o `messaging.json` (Onda B6) não tem como pôr a senha aberta sem trocar o tipo. **Fechado em 21/11/2026 (Onda B6-A):** até aqui o campo em claro era ignorado em silêncio por quem lia o bloco — o lojista escrevia `password`, nada reclamava e a ponte nascia sem senha. Agora a fábrica recusa por conteúdo: um bloco que traga `password` ou `bridge_key` em claro não monta o motorista, e a mensagem nomina o campo e o conserto (`password_sealed`) sem nunca escrever o valor no log.
- **Ler** prefere IMAP com cursor de `UID` e cai para POP3 quando só existe POP3. Cada recado já lido leva um carimbo (o `Message-ID`, ou a impressão SHA-256 do corpo quando ele falta) e o que a ponte aprendeu é pouco e limitado: 400 carimbos lidos e 200 recibos. O arquivo é o caminho que `state_path` receber — com `state_path` vazio a ponte funciona, mas esquece o cursor entre uma execução e outra. Cabe à Onda B6 apontar esse caminho para a pasta de dados do usuário. **Feito em 21/11/2026 (Onda B6-A):** sem `state_path` no bloco, a fábrica escreve `<pasta de dados do Gaspar>/bridge-smtp.state` — a mesma pasta da fila e da chave, respeitando `GASPAR_HOME`. Medido: montar a ponte e consultar a saúde dela não criam o arquivo; a primeira escrita é a barra fechando e gravando o cursor.
- **O corpo** é um envelope AES-256-GCM em base64 de uma linha só, com a chave da ponte também selada no cofre. Assunto e `Message-ID` carregam só o identificador do pedido, e o `To` é a caixa do balcão: o número do cliente não aparece em claro em nenhum byte do e-mail, e há teste para isso.
- **Os quatro desfechos** valem aqui, com um refinamento: a falha é classificada pela etapa. Conexão recusada, login recusado ou recusa explícita do servidor são `recusado` (nada chegou ao servidor, refazer é seguro); cair no meio do envio é `incerto` (o pedido pode ter passado, e a barra nunca reenvia sozinha). Um comprovante que chega depois pela mesma caixa resolve o `incerto` sem reenviar.
- **`health()` não abre conexão nenhuma**, de propósito: ela responde pelo estado da configuração. É por aí que o painel e o `/v2/health`, quando a ponte estiver ligada, poderão dizer se ela está de pé sem gastar uma ida ao servidor de e-mail a cada consulta.

A prova de que a ponte desligada não fala com o mundo é `tests/test_messaging_email.py`: `ZeroConexaoTeste` monta o motorista **sem** dublês — então são os caminhos reais de saída do módulo que estão na mira — com oito pontos da biblioteca padrão gravando e recusando (`smtplib.SMTP`, `smtplib.SMTP_SSL`, `imaplib.IMAP4`, `imaplib.IMAP4_SSL`, `poplib.POP3`, `poplib.POP3_SSL`, `socket.create_connection`, `socket.getaddrinfo`), e exige lista vazia depois de `health`, `submit`, `poll_inbound`, `resolve_uncertain` e `shutdown`. Um teste irmão liga a ponte e confere que o mesmo gravador registra exatamente uma tentativa, nomina o servidor e o endereço (`smtplib.SMTP_SSL smtp.test.invalid` na saída, `imaplib.IMAP4_SSL imap.test.invalid` na leitura) — sem essa contra-prova, o verde de antes poderia ser decorativo.

Cobertura medida no gate local (Python 3.13, `GASPAR_HOME` em área de passagem): 53 testes em `test_messaging_email.py`, 498 testes no total, `smtp_email.py` em 91% e o repositório em 82% contra o piso de 70% do Portão.

A ponte ainda é código vivo mas não instalado: nada em `config.py`, `local_api.py` ou no painel a referencia, então nenhum balcão a aciona hoje. O ligamento (escolher a conta, testar o acesso, mostrar o estado na aba Celular) é a Onda B6. **Cumprido no código em 21/11/2026 (Ondas B6-A e B6-6):** escolher a conta e acionar a ponte já existe — pelo `messaging.json` na B6-A (com `enabled: true` e `transports.HUB = "smtp_email"`, a fábrica monta o motorista, aponta o estado para a pasta de dados e a fila despacha por ele) e, desde a B6-6, **o painel também a referencia**: a caixa de e-mail da loja é uma das opções do seletor e a janela dos ajustes escreve a conta. O que falta hoje tem um nome só: a **validação contra uma caixa postal de verdade** — a tela da B6-6 (21/11/2026) deixou de ser falta, mas nenhum teste daqui substitui aquela prova.

**Ela também entrou na lista de empacotamento (D6).** Como o PR #9 já está na `master`, o guardão `tests/test_packaging_manifest.py` compara a lista dos dois specs com o conteúdo de `gaspar/messaging/` a cada Portão — um módulo novo sem linha no spec deixa o Portão vermelho. Esta onda acrescenta `gaspar.messaging.transports.smtp_email` nos dois specs: a mensageria passa de 13 para 14 módulos listados, e a varredura do arquivo gerado (o passo `Conferir os módulos da mensageria no pacote (D6)` dos dois jobs de pacote) é quem prova a presença dentro do executável, não a lista.

### Canal local (`android_lan`)

Gravado em 2026-11-20 (Onda B4). `gaspar/messaging/transports/android_lan.py` traz o `AndroidLanTransportDriver`: a barra de mensagens 2.0 passando a falar com o celular que **já está pareado** na rede local da loja, pelo mesmo TCP da 1.7. Não é canal novo — é o velho canal com uma entrada a mais.

O que foi medido antes de escrever, no código publicado do aplicativo Android (`GatewayListenerService.java`, `E2ECrypto.java`, `SmsReceiptSender.java`): o celular é o **servidor** TCP na porta 49998; o quadro é de quatro bytes com o tamanho, corpo cifrado com AES-256-GCM pela chave do pareamento (`crypto.key_from_base64`: base64, SHA-256 se curta, 32 bytes); dentro vai o pedido `{action, number|envelope, id, ts, base, seq}`; o envelope ponta a ponta usa EC P-256 efêmero + HKDF-SHA256 e **tem como AAD o `id` da mensagem em ASCII**; e o ACK só é escrito depois do `SmsManager.sendTextMessage`. Nada de `gaspar/sms/` foi alterado — o módulo novo **importa** `crypto`, `e2e`, `protocol` e `discovery` da v1.7 e escreve só o enquadramento e a leitura do ACK, que é onde o `origem` precisa entrar (o `PhoneClient.send()` da 1.7 não tem como carregá-lo).

- **`origem` (PDV ou HUB) vai no comando e dentro do envelope.** O aplicativo 1.7 lê as chaves que conhece com `optString`/`optLong` e ignora as outras, então o campo extra não quebra nenhum aparelho já instalado — é isso que permite mandar a barra nova para o balcão sem obrigar ninguém a atualizar o celular.
- **Número e texto só existem dentro do envelope** fechado na chave pública do celular. `exigir_e2e` nasce **ligado**: um aparelho que ainda não entregou a chave pública é recusado (`recusado`), em vez de receber o pedido em claro como na 1.7. O modo antigo continua disponível para quem escrever `exigir_e2e: false`.
- **A sequência é crescente e o celular recusa a que for igual ou menor que a última vista** (`error: "pedido repetido"`). É essa recusa — medida no código do app, não presumida — que transforma `recusado` em prova de que nada saiu duas vezes. Por isso um pedido `incerto` nunca é reenviado por este motorista, e a rodada de endereços para no primeiro `incerto`: empurrar o mesmo quadro no próximo IP seria duplicar o SMS e a cobrança do lojista.
- **Os quatro desfechos:** `aceito` quando o celular respondeu `ok`; `recusado` enquanto nada chegou ao rádio (meio desligado, sem pareamento, sem chave, sem endereço na rede, texto que o UTF-8 não escreve, recusa dita pelo próprio aplicativo); `incerto` quando o quadro foi empurrado na conexão e a resposta não voltou; `indisponivel` quando falta segredo de pareamento à origem.
- **Credencial por origem é meia-verdade hoje, e está escrita como tal.** `LanSettings` aceita `segredos_por_origem` e cai para o `segredo` único quando a origem não tem a sua, porque o aparelho 1.7 guarda **uma** chave por dispositivo em `SharedPreferences`, em texto claro. O isolamento real de credenciais no canal Wi-Fi só existe quando o APK 2.0 (Onda B5) passar a guardar uma por origem. Os testes desta onda provam o que o código já faz — cada origem usa o segredo que tem, e na falta usa o comum — e não provam o que ainda não foi escrito. **Acrescido em 20/11/2026 (Onda B5):** a metade do celular foi escrita. O app 2.0 guarda o segredo do PDV e o do Hub em entradas separadas (`gateway_shared_secret_pdv` / `gateway_shared_secret_hub`, lidas por `SmsPreferences.getGatewaySecretFor`) e abre uma por vez — a chave que descifra o recado é a autora, e a origem declarada dentro do pedido ainda tem de bater com ela (`PareamentoPorOrigem`), no Wi-Fi e na ponte de e-mail pela mesma chave. Medido no aparelho: as duas chaves gravadas e lidas por origem, e a linha do painel mudando de "Nenhum computador está ligado" para "PDV e HUB". Duas coisas esta nota **não** muda: o armazenamento continua `SharedPreferences` em texto claro (a cifra de Keystore do app 2.0 cobre a senha do Wi-Fi e a senha do aplicativo, não o segredo de pareamento), e como o QR de pareamento não carrega origem (`CARACORE-SETUP|ip|porta|chave|token|licenca`), o caminho de um pareamento por QR segue sendo chave única — que é exatamente o caso em que a queda para o `segredo` comum continua viva.
- **A volta é por comprovante, não por resposta.** `abrir_comprovante()` abre exatamente o blob AES-GCM que o app 1.7 POSTa em `/api/mobile/receipt`, tenta cada credencial (a da origem e a comum), traduz `sent/delivered/failed` para os estados da fila e guarda no máximo 200 em memória, por ordem de chegada. `resolve_uncertain()` responde só o que o celular contou e nunca reabre a rede.
- **`health()` não abre conexão nem faz descoberta**, de propósito: lê só a configuração, para o painel poder perguntar sem incomodar ninguém na rede. Quem abre soquete é `submit()`.

A prova é `tests/test_messaging_lan.py` (66 testes): o grupo `SaudeTeste` monta o motorista com **oito pontos da rede travados** (`socket.create_connection`, `socket.socket`, `socket.getaddrinfo`, `android_lan.discover` e os demais) e exige lista vazia de tentativas depois de `health`, `submit` desligado e `resolve_uncertain` — com teste irmão que liga o meio e confere que o mesmo gravador registra a tentativa, senão o verde seria decorativo. `PontaAPontaTeste` sobe um **aplicativo Android de mentirinha em TCP real em 127.0.0.1**, com par de chaves P-256 de verdade: ele abre o envelope com a chave privada, confere o AAD e devolve o ACK cifrado pelo mesmo caminho. É nesse grupo que se prova que o número e o texto não aparecem em claro no comando, que PDV e HUB chegam marcados cada um pela sua credencial, que a credencial de fora não abre a caixa e que celular mudo ou lento deixa o pedido em dúvida com o comando recebido **uma** vez.

Sonda de mutação (`.auditoria/b4_mut.py`, registro em `.auditoria/b4_mutacoes.log`): catorze quebras de uma propriedade cada — `origem` fora do comando, `origem` fora do envelope, uma credencial só para todas as origens, dúvida virando recusa, dúvida reenviada no endereço seguinte, sequência que não sobe, meio desligado que envia mesmo assim, comprovante sem teto, envelope opcional, `health()` abrindo rede, recusa de sequência ignorada, texto impossível maquiado com `errors="ignore"`, comprovante que não se reordena e cabeçalho de quadro perdido. **14/14 vermelhas**, cada grupo voltando a verde depois de restaurar. Fica a armadilha achada no caminho, porque ela morde de novo: uma mutação que troca `!=` por `==` não muda o tamanho do arquivo, e o `.pyc` é invalidado por (mtime em segundos, tamanho) — a primeira versão da sonda deu verde falso por ler o bytecode da rodada anterior. A sonda agora apaga `__pycache__` e roda com `PYTHONDONTWRITEBYTECODE=1`.

Cobertura medida no gate local (Python 3.13, `GASPAR_HOME` em área de passagem): `android_lan.py` em 99% (sobram a descoberta UDP real e dois ramos de rede que o soquete de mentira não reproduz), 590 testes no total e o repositório em 83% contra o piso de 70% do Portão.

Quando esta seção foi escrita (Onda B4) o canal era código vivo mas não instalado: nada fora dos testes referenciava `android_lan`, e quem enviava SMS pela rede local ainda era a ponte 1.7. **Isso mudou.** A escolha do motorista por origem na configuração, o estado na aba Celular e a rota do comprovante até `abrir_comprovante` foram abertos como Onda B6. **Cumprido em 21/11/2026 (Ondas B6-A e B6-5):** a escolha por origem no `messaging.json` existe e é ela que decide quem fica com o celular pareado — com `enabled: true` e uma origem em `android_lan`, a fábrica monta o motorista, o painel (`gaspar/app.py`) liga a barra e a ponte 1.7 cede a vez (ver «Convivência com o motor 2.0 (a porta 49998)») — e a volta do celular chegou ao `abrir_comprovante` (ver «A volta do celular (porta de comprovantes)»). Faltava o estado na aba Celular em linguagem de lojista: **cumprido no mesmo dia pela Onda B6-6** (seletor por origem, cinco frases de status e **Testar acesso**). Continua sem instalação: `enabled` nasce `false`, então nenhum balcão aciona nada disso antes de escolher.

**Também entrou na lista de empacotamento (D6):** `gaspar.messaging.transports.android_lan` nos dois specs, que passam de 14 para 15 módulos listados.

### Ligamento por arquivo (`messaging.json`) — Onda B6-A

Gravado em 2026-11-21. Até aqui nenhum código do produto construía um motorista: a fila sabia o nome escolhido por origem, mas não tinha como montar o que havia por trás do nome. A onda fecha esse buraco e liga a barra ao aplicativo.

**A fábrica** é `gaspar/messaging/transports/factory.py`. `construir(nome, ajustes, vault=…, home=…)` monta `android_lan`, `loopback` e `smtp_email`; `usb_modem` recusa com o motivo próprio («o motorista do modem USB ainda não foi escrito»), e um nome que a fábrica não conhece responde o que ela sabe montar. `montar_registry(registry, config, …)` registra todo motorista que alguma origem citou. Um bloco recusado **não derruba a barra**: o motorista fica de fora, a origem que o escolheu fica desligada e o motivo vai para o log — erro de digitação no arquivo do Hub não tira o PDV do ar. Nada na fábrica abre conexão: montar é ler ajuste e abrir selo.

**O serviço** ganhou `MessagingService.montar_meios()`, chamado no construtor e de novo em `start()`. Com `enabled: false` (o padrão de fábrica) ele devolve lista vazia sem tocar em nada: nenhum arquivo de estado nasce, nenhuma caixa postal é lida, nenhum celular é procurado. Quem injeta um registro pronto — os testes e qualquer integrador — manda sozinho no que está ligado, e a fábrica não é chamada.

**O painel** importa o pacote dentro do mesmo `try` que protege a ponte de SMS (`MESSAGING_AVAILABLE` / `MESSAGING_IMPORT_ERROR`): módulo ausente ou quebrado desliga a peça e escreve uma linha no log, sem janela de erro para o lojista. `_init_messaging()` roda 900 ms depois de a janela abrir, lê o `messaging.json` e, quando o arquivo manda, `_start_messaging()` liga o motor. `quit()` fecha a barra junto com o resto.

#### Estrutura do `messaging.json`

Dois blocos, cada um na sua chave: `transports` diz **por origem** qual motorista aquela origem usa, e `transport_settings` diz **por motorista** como ele é montado.

```json
{
  "enabled": true,
  "transports": { "PDV": "android_lan", "HUB": "smtp_email" },
  "transport_settings": {
    "android_lan": { "ligada": true, "exigir_e2e": true, "segredo_sealed": "…", "chave_celular": "…" },
    "smtp_email": {
      "enabled": true,
      "smtp_host": "smtp.gmail.com", "smtp_port": 465, "smtp_security": "ssl",
      "user": "balcao@exemplo.com.br", "password_sealed": "…",
      "imap_host": "imap.gmail.com", "bridge_key_sealed": "…"
    }
  }
}
```

Os nomes de campo são os dos `dataclass` de cada motorista (`LanSettings` usa `ligada`, `EmailSettings` usa `enabled` e `user`), e o que a fábrica não conhece fica de fora da leitura.

- **`transports` é por origem**, como pediu o dono: cada sistema escolhe o seu meio, e a origem que não cita nada fica desligada. `""` vale como «sem meio».
- **`transport_settings` é por motorista**, e isso é uma escolha registrada. Ler os ajustes também por origem permitiria escrever «PDV numa caixa postal, HUB em outra» — e o resultado seria **dois `EmailBridgeDriver` lendo a mesma caixa e cada um comendo os comprovantes do outro**, porque cada um tem seu cursor de `UID` lido. Um motorista por tipo é o que o resto do motor já assume (as credenciais, a fila e o `/v2/health` separam por origem; o aparelho e a caixa postal são um só). A partilha está gravada como teste, `test_duas_origens_no_mesmo_motorista_compartilham_uma_soa_caixa`, que exige `assertIs` entre os motoristas das duas origens.
- **Os dois exemplos do dono funcionam.** Hub no e-mail e PDV na LAN: os dois blocos acima. Ambos compartilhando a mesma caixa postal: `"transports": { "PDV": "smtp_email", "HUB": "smtp_email" }` com um bloco só de ajustes — que é exatamente o comportamento certo, uma caixa = um cursor.
- **O que ainda não é expressável:** duas caixas postais *diferentes* para PDV e HUB. Enquanto houver um motorista por tipo, isso não entra no arquivo. No Wi-Fi a separação por origem já existe e é o contorno: `segredos_por_origem_sealed` dá uma chave de pareamento por origem dentro do mesmo `android_lan`.
- **De onde vêm os dois campos do Wi-Fi.** `segredo` é a `shared_secret_b64` e `chave_celular` é a `phone_public_key_b64` do `sms_config.json` da 1.7. O primeiro é segredo e por isso só entra selado; o segundo é chave pública e pode ir em claro. Faltando a `chave_celular` com `exigir_e2e: true` (o padrão), o motorista monta mas fica indisponível — «celular sem chave de criptografia; pareie o celular de novo» — e a origem não envia. Medido com o exemplo acima escrito sem esse campo.

#### Segredo só selado

A recusa é do tipo que não deixa o vício entrar: o bloco que trouxer `segredo`/`segredos_por_origem` (Wi-Fi) ou `password`/`bridge_key` (e-mail) em texto aberto **não monta o motorista**. A mensagem nomina o campo e o conserto (`segredo_sealed`), nunca o valor — quem lê o log não vê segredo. Os selos são abertos em memória na montagem e gravados de volta só selados; um selo de outra máquina falha com «não abriu com a chave desta máquina; pareie de novo ou resele».

Enquanto não havia painel, quem escrevia o arquivo selava à mão com o cofre da fila. A partir da Onda B6-6 a tela faz isso sozinha (ver a seção da B6-6); o caminho manual continua valendo para preparar uma máquina por linha de comando:

```python
from gaspar.paths import data_dir
from gaspar.messaging.vault import Vault, KEY_FILENAME   # messaging-vault.key

vault = Vault.load_or_create(data_dir() / KEY_FILENAME)
print(vault.seal("senha de app da caixa postal"))        # cola o resultado em password_sealed
```

O cofre é o mesmo que cifra a fila, então o `messaging.json` pode ir por e-mail ou para outro balcão sem levar segredo nenhum: sem a `messaging-vault.key` da máquina, nada abre.

#### Estado da ponte de e-mail

Sem `state_path` dito no bloco, a fábrica aponta o cursor da ponte para `<pasta de dados do Gaspar>/bridge-smtp.state` (respeitando `GASPAR_HOME`). Isso fecha a pendência registrada na Onda B3 («cabe à Onda B6 apontar esse caminho para a pasta de dados do usuário») e evita o pior caso: o estado cair no diretório de trabalho de quem abriu o Gaspar. Montar a ponte e perguntar a saúde dela não criam esse arquivo — a primeira escrita é o fechamento da barra gravando o cursor.

#### O que ficou de fora desta onda

A Onda B6 foi aberta pelo dono em 2026-11-21 dividida em seis itens, com B6-A = B6-1 a B6-4 e B6-5/B6-6 para a onda seguinte. Como cada um foi medido:

| Item | O que é | Estado |
| --- | --- | --- |
| B6-1 | Fábrica que monta o motorista a partir do nome escolhido. | **Cumprido em 21/11/2026** — `transports/factory.py`, com `usb_modem` recusando por nome. |
| B6-2 | Estrutura do `messaging.json`: meio por origem e ajustes por motorista. | **Cumprido em 21/11/2026** — `transports` + `transport_settings` em `config.py`. |
| B6-3 | Ajustes de cada motorista lidos do arquivo, com segredo só selado e estado da ponte na pasta de dados. | **Cumprido em 21/11/2026** — `LanSettings.from_dict`, recusa de claro, `bridge-smtp.state`. |
| B6-4 | Ligamento no aplicativo: o `gaspar/app.py` construindo o serviço, respeitando a precedência da 49998 e entrando nos specs (D6). | **Cumprido em 21/11/2026** — `_init_messaging`/`_start_messaging`/`_stop_messaging`, `convivencia.py`, 17 módulos nos dois specs. |
| B6-5 | Rota do comprovante: dar a `abrir_comprovante` um chamador em produção (a volta do celular chega à fila). | **Cumprido em 21/11/2026** — `messaging/comprovantes.py` chamado pela porta 8766 (ver seção própria abaixo). |
| B6-6 | Tela do lojista: escolher meio por origem, testar acesso, mostrar o estado do motorista na aba Celular e selar o segredo sem editar arquivo. | **Cumprido em 21/11/2026** — quadro da barra na aba **Celular / SMS**, seletor por origem, botão **Testar acesso** e a janela dos ajustes que sela a senha (ver seção própria abaixo). |

Fora da conta da B6, continuam abertos: `usb_modem` (sem motorista), a publicação do app Android 2.0 (etiqueta `android-v2.0`, APK assinado e release — travada pela custódia da chave de assinatura) e a validação real (caixa de e-mail de verdade, QR carregando a origem e aparelho físico). Nada disso é decidível por código: os três dependem de máquina, chave e aparelho.

**Medido no gate local** (Python 3.13, `GASPAR_HOME` em área de passagem): 645 testes OK e 1 pulo, repositório em **83%** e `gaspar/messaging` em **94%** contra o piso de 70% do Portão; os dois módulos novos em `convivencia.py` **100%** e `transports/factory.py` **97%**. Os 55 testes novos são 31 em `tests/test_messaging_factory.py`, 12 em `tests/test_messaging_convivencia.py` e 12 em `BarraMensagens20Tests` (`tests/test_app.py`). Um dos 31 (`test_o_exemplo_do_manual_monta_os_dois_motoristas`) grava o JSON de exemplo desta seção — os blocos de `PDV` no celular e de `HUB` no e-mail —, monta os dois meios e exige os dois disponíveis: se um campo mudar de nome, o exemplo publicado fica vermelho aqui antes de enganar alguém na mão. **D6:** `gaspar.messaging.convivencia` e `gaspar.messaging.transports.factory` entraram nos dois specs, que vão de 15 para 17 módulos listados; o guardão compara a lista com `gaspar/messaging/` a cada Portão.

Fica um ponto de honestidade sobre a máquina de medição: a suíte Python em Windows tem as duas fraquezas já registradas (o caso do telefone offline que estoura o tempo da suíte e o 413 do `_read_body` que derruba o soquete com `WinError 10053`). Nesta onda o segundo apareceu em **3 das 5 execuções completas** nesta máquina e em **1 de 6 execuções isoladas do mesmo caso sobre o `763d010`** — o commit da `master` sem nenhuma linha desta onda —, então é herdado, não introduzido aqui, e continua medido sem correção deliberada (as duas fraquezas da suíte em Windows seguem na fila). O verde de 645 testes acima é de uma execução completa sem o tropeço; o Portão roda em `ubuntu-latest`, e nos Portões verdes desta fase (PR #10, #11 e #12) nenhum dos dois casos apareceu.

### A volta do celular (porta de comprovantes) — Onda B6-5

Gravado em 2026-11-21. A B4 escreveu `abrir_comprovante()` no motorista `android_lan` e a prova ficou nos testes: em produção ninguém chamava. A B6-A decidiu quem fica com o celular e, ao fazer isso, abriu um buraco que esta onda fecha.

**O buraco, medido no código e não presumido.** `_start_messaging()`, ao ver o celular reservado, chamava `_stop_sms_services()` — que fecha as duas coisas da 1.7: o trabalhador que envia **e** o `SmsHttpServer` da porta 8766. Na 1.7 os dois andam juntos e está certo. Na barra 2.0 não: quem envia passou a ser o motorista, mas a porta 8766 é a única porta por onde o celular devolve o recibo. Fechar a porta com o motor ligado deixava a fila 2.0 sem volta nenhuma — e derrubava junto `/api/mobile/key`, `/api/mobile/diagnostic` (o pareamento) e `/api/health`. Um celular pareado depois disso não se pareava mais.

**A porta escolhida é a que já existe.** Em vez de um segundo servidor, a 1.7 ganhou dois ganchos opcionais, ambos desligados por padrão, e a barra 2.0 se pendura neles:

| Gancho | O que faz | Sem gancho |
| --- | --- | --- |
| `on_receipt` | recebe o blob cifrado do POST `/api/mobile/receipt` antes de qualquer tentativa de abrir | a 1.7 descifra e cuida, como sempre |
| `send_blocker` | devolve um motivo para recusar o envio nesta porta (`503` + `codigo: "celular_reservado"`) | devolve vazio e o envio segue |

Por que reaproveitar em vez de montar outra porta: o aplicativo Android conhece **uma** URL de volta — a que gravou no pareamento (`ScanSetupActivity` → `setPdvBaseUrl`) e que cada comando pode atualizar pelo campo `base` (`GatewayListenerService`); o recibo sai para `<base>/api/mobile/receipt` (`SmsReceiptSender`). Dois servidores não disputam a mesma 8766, e um endereço novo obrigaria cada aparelho a ser pareado de novo por uma vantagem que não existe. Consequência honesta: **um celular pareado ontem continua fechando a volta hoje sem refazer nada**, e a rota nova não tem nenhuma URL própria para divulgar.

**O ponto único que junta as pontas** é `gaspar/messaging/comprovantes.py`. `aplicar_comprovante(store, registry, corpo)` pergunta a cada motorista registrado se ele sabe abrir aquele recibo (`abrir_comprovante` / `comprovante_de`), procura o pedido na fila de cada origem e escreve o estado com `store.mark(..., motivo="comprovante do celular")`. O `MessagingService` expõe isso como `registrar_comprovante(corpo)`, e é essa função que o painel entrega à porta. As regras que a onda jurou por teste:

- **A origem vem da fila, nunca do celular.** O recibo carrega só o `id`; `_procurar()` atravessa `ORIGENS` até achar o pedido. Um aparelho não escolhe de qual produto ele fala.
- **Recibo que não é daqui cai na 1.7.** Chave que não abre, id que não está na barra: `aplicar_comprovante` devolve `False`, a porta passa adiante e a loja antiga atende do mesmo jeito. Prova: um recibo cifrado por outra chave chega e a ponte falsa registra `("job-da-17", "delivered")`.
- **Estado que já está fechado não reabre.** `entregue` é terminal; um `enviado` que chega depois é respondido sem escrever. Recibo repetido escreve uma vez.
- **Só os três estados do comprovante.** `enviado`/`entregue`/`falhou` — e a equivalência com o vocabulário do motorista (`ESTADO_ENVIADO/ENTREGUE/FALHOU`) está presa por teste, senão as duas listas envelhecem separadas. Estado inventado: responde sem escrever.
- **Nada aqui reenvia.** A volta só escreve o que o celular contou; a política de `incerto` da B4 continua intacta.
- **Motorista quebrado não tampa a porta.** O que estoura dentro de `abrir_comprovante` é engolido e a porta continua; um motorista sem o método não impede o que tem.

**O painel** passou a ter três métodos. `_ligar_porta_de_comprovantes()` instala os ganchos num servidor que já está de pé, ou monta e liga um quando a reserva pegou o celular antes de a 1.7 subir. `_parar_envio_da_ponte()` desliga só o trabalhador da fila antiga, sem fechar a porta. `_motivo_de_envio_cedido()` é a resposta que o produto lê: `503` com «O celular desta casa envia pela barra de mensagens 2.0 e a ponte antiga esta cedida. Envie para http://127.0.0.1:8767/v2/messages informando a origem.» Uma falha no gancho devolve vazio — não tranca o balcão que ainda pode enviar.

**Ordem de subida, que é o caso real.** O painel liga a 1.7 em 450 ms e a barra 2.0 em 900 ms: no arranque comum a porta 8766 já está de pé quando o motor toma o celular, e o caminho ali em cima é só instalar ganchos. O outro caminho — o operador acende o motor com a ponte desligada, ou o `enabled: true` chega antes de qualquer 1.7 — é o que monta o servidor na hora. Os dois têm teste.

**O que esta onda não é.** Não é a resposta do cliente: texto de quem responde ao SMS continua sem caminho pelo Wi-Fi, porque o aplicativo Android não tem `RECEIVE_SMS` (removido de propósito na 1.4). «Ida e volta» aqui é **comprovante de entrega**, e é isso que o lojista vê virar `entregue` na fila. Também não abriu janela de novidade anti-repetição: `/api/mobile/receipt` não pede `ts` nem nonce nem assinatura de cabeçalho — ele é autenticado pela própria cifra (só abre com o segredo do pareamento), que é o contrato da 1.7 desde antes desta onda e que ela mantém igual. E não encosta no e-mail: `smtp_email` já tinha a sua volta, pelo `poll_inbound` da ponte.

**Uma regra da B6-A precisou ser afiada, e isso mexeu em teste já verde.** A precedência foi gravada como «a 1.7 cede o celular», e três casos de `tests/test_app.py` tinham sido escritos como «a 1.7 inteira cai»: eles afirmavam `sms_server is None` e que a linha de reserva era a última do log. Com a porta de comprovantes de pé, esses três passaram a afirmar o contrato novo — o servidor continua vivo com os ganchos instalados, a fila antiga é que para. Os outros 98 casos de `test_app.py` não foram tocados. Nada do que a B6-A decidiu sobre **quem** fica com a 49998 mudou: só o que acontece com a porta 8766 depois disso.

**Medido no gate local** (Python 3.13, `GASPAR_HOME` em área de passagem): **671 testes OK** e 1 pulo em 71,8 s, repositório em **83%** e `gaspar/messaging` em **94%** contra o piso de 70% do Portão. Os módulos da volta: `messaging/comprovantes.py` **96%**, `messaging/service.py` **97%**, `sms/server.py` **81%**, `app.py` **88%**. `transports/android_lan.py` ficou em **99%** com **346** sentenças — a volta não acrescentou uma linha ao motorista, porque `abrir_comprovante` já estava lá desde a B4 e o que faltava era chamador. Os 26 testes novos são 23 em `tests/test_messaging_comprovantes.py` (13 em `ComprovanteNaFilaTeste`, 8 em `PortaDeComprovantesTeste` com um `SmsHttpServer` real em `127.0.0.1` e porta efêmera, 2 em `ServicoRegistraComprovanteTeste`) e 3 em `tests/test_app.py`, que vai de 101 para 104.

**D6:** `gaspar.messaging.comprovantes` entrou nos dois specs, que vão de 17 para **18** módulos listados; o guardão `tests/test_packaging_manifest.py` continua verde comparando a lista com `gaspar/messaging/`.

**A fraqueza de Windows medida de novo, e agora com nome mais largo.** O ponto registrado na onda passada («o `_read_body` que derruba o soquete com `WinError 10053`») não é só o 413 do corpo enorme: é **qualquer resposta dada antes de o corpo ser lido**. Nesta medição o mesmo abort estourou em `test_rota_desconhecida` — um `POST /v2/nada`, que responde 404 na linha de despacho sem tocar no corpo — e o caso ficou **2 de 3** execuções do módulo sozinho nesta árvore. Que é herdado, e não entrou aqui, foi provado no commit pai com a mesma imagem: num worktree limpo do `2a975bd` (sem nenhuma linha desta onda) o `tests.test_messaging_api` falhou **2 de 4** e depois **3 de 3**, com o abort em outro caso da mesma classe (`test_corpo_vazio_ou_enorme_ou_fora_de_json`) — mesma classe, mesma exceção, caso diferente a cada rodada, que é a assinatura de uma corrida e não de um contrato errado. O verde de 671 acima é de uma execução completa sem o tropeço, e foi reconfirmado no commit deste lote: a primeira passada naquele commit ainda levou o abort (671 com 1 erro), a segunda fechou em **671 OK, 1 pulo e 83% em 71,9 s** — o placar citado é o dessa segunda passada. A correção tem cara (drenar o corpo antes de responder, ou fechar com `SO_LINGER`/`shutdown` limpo) e continua fora de escopo: mexe no `local_api.py` da Alpha, já assinado, e no `_read_body` da 1.7.

### A tela do lojista (meio por origem, senha selada, prova de acesso) — Onda B6-6

Gravado em 2026-11-21. A B6-A ensinou o programa a ler o `messaging.json`; a B6-5 deu ao celular um caminho de volta. Faltava alguém **escrever** o arquivo, e quem escreve é o dono da loja, não quem edita JSON. Até esta onda, ligar a barra 2.0 numa loja significava editar texto na mão, e as duas limitações registradas na B6-A eram consequência disso: selar senha com um trecho de Python e não ter como saber se o canal escolhido responde.

#### Onde a barra mora na tela

Dentro da aba **Celular / SMS**, um quadro próprio — **Mensagens pelo computador (barra 2.0)** — e não uma aba nova: é ali que o lojista já ia procurar pelo celular. Cinco peças, todas em linguagem de loja:

| Peça da tela | O que é por trás |
| --- | --- |
| Caixa **Ligar a barra de mensagens** | `enabled` no arquivo |
| **CaraCore PDV envia por** / **CaraCore Hub envia por** (um seletor por programa) | `transports.PDV` / `transports.HUB` |
| Uma linha de resposta debaixo de cada seletor | a saúde daquele motorista, lida no motor vivo |
| Botão **Testar acesso** | `testar_acesso()` do motorista, sem enviar nada |
| Botão **Ajustar celular e caixa de e-mail** | a janela que escreve `transport_settings` |

A palavra *motorista*, o nome do arquivo, o número da porta e os apelidos técnicos (`android_lan`, `smtp_email`) não aparecem em nenhuma linha da tela. O vocabulário é este, e é o que o seletor oferece, nesta ordem:

| No arquivo | Na tela |
| --- | --- |
| — | Sem canal (este programa nao envia) |
| `android_lan` | Celular pela rede da loja |
| `loopback` | Ensaio neste computador (nada sai para a rua) |
| `smtp_email` | Caixa de e-mail da loja |

As linhas de resposta dizem sempre a mesma coisa em cinco frases, e nenhuma delas empurra o lojista para um termo que ele não pode procurar:

- `CaraCore PDV nao envia mensagens.` — nenhuma origem escolhida;
- `… a barra esta desligada, nada sai.` — `enabled: false`, que é o padrão de fábrica;
- `… a barra nao conseguiu subir (veja o registro de eventos).` — `enabled: true` com o motor morto (bloco recusado pela fábrica, porta ocupada);
- `… pronto para enviar - <detalhe> (<motivo>)` — o canal respondeu à pergunta de saúde;
- `… ainda nao esta pronto: <motivo>` — respondeu indisponível, com o motivo que o próprio motorista deu.

Quando alguma origem está no celular, a linha ainda fecha com `| o celular esta com a barra; a ponte antiga esta cedida` — a frase que a B6-A/B6-5 decidiu, dita em palavras de loja, porque é isso que explica por que a janela de cima parou de enviar.

#### O que a tela não oferece, e por quê

- **`usb_modem` não aparece no seletor.** Não tem motorista; um botão para um canal inexistente é promessa de loja que o código não assina. Continua listado em `MEIOS_SEM_CODIGO` na fábrica, que recusa por nome.
- **A terceira cifra do e-mail (`plano`) não é oferecida.** `smtp_security` só aceita `ssl` (465) e `starttls` (587) pela tela; `plano` existe para tubo de teste local e **sobrevive** se já estava no arquivo — a janela converte rótulo por rótulo e um valor que ela não oferece volta inteiro, senão abrir e salvar apagaria o ajuste de quem sabe o que fez.
- **Ajuste fino fica no arquivo:** `porta` e os três tempos do Wi-Fi; `from_address`, `message_id_domain`, `imap_port`, `pop3_port`, `mailbox`, `max_poll_messages` e `state_path` do e-mail, além de `segredos_por_origem_sealed` (a chave própria por origem, que é texto de integrador, não de balcão).
- **Nome que a tela não conhece não é reescrito.** Um `usb_modem` que alguém colocou na mão aparece no seletor sem maquiagem e sai do arquivo igual depois de qualquer troca — provado por teste, porque o caminho fácil (mapear rótulo → nome) apagaria o que não mapeia.

#### A janela dos ajustes escreve por cima, não do zero

É o ponto que mais facilmente comeria trabalho alheio, e foi pego na autoauditoria desta onda, não em produção. `_colher_canal()` parte de `dict(guardados)` — o bloco que já está no arquivo — e só por cima põe as chaves que a tela mostra. Reconstruir o bloco a partir da tela apagaria, a cada clique em **Salvar**, tudo o que a tela não mostra: `porta`, `timeout`, `mailbox`, `state_path`, `max_poll_messages` e o `segredos_por_origem_sealed` que dá uma chave por origem. O teste `test_campo_em_branco_mantem_o_selo_e_o_arquivo_nao_perde_ajuste_fino` grava um bloco com `mailbox` e `max_poll_messages`, salva sem digitar nada e exige os dois de volta.

O mesmo cuidado vale para os quadros de marcar. Cada linha da tabela de campos carrega o **padrão do próprio motorista**, não um `False` genérico: `descobrir` e `exigir_e2e` nascem ligados no `LanSettings`, e gravá-los desligados por descuido mudaria a segurança do canal (procurar o celular na rede e exigir envelope ponta a ponta) sem ninguém pedir. `test_a_janela_preserva_o_que_so_o_motorista_sabe_ler` fecha a janela, salva e lê o arquivo.

O segredo tem três regras, todas presas por teste:

1. **o campo de senha entra vazio, sempre** — o que está selado não volta para a tela;
2. **em branco quer dizer «não mexi aqui»**: o selo antigo continua no arquivo; digitado, o valor é selado por `Vault.seal` do cofre da fila antes de qualquer escrita, e o texto aberto não passa nem pela memória do arquivo;
3. **selo vazio não é gravado** — um `"password_sealed": ""` no arquivo faria a fábrica chamar `vault.open("")` e recusar o canal inteiro.

Sem cofre aberto (pasta de dados indisponível, chave corrompida), a janela **recusa salvar** com «Sem o cofre deste computador nao da para guardar a senha digitada… Nada foi alterado.» e fica aberta para tentar de novo: perder o texto digitado seria jogar o lojista de volta para o e-mail do banco.

Um detalhe honesto do caminho texto → número: a tela escreve a porta como texto, então uma porta deixada em branco vira `"smtp_port": ""` no arquivo. `EmailSettings._porta` converte para o padrão do motorista (465) — e `test_a_porta_em_branco_monta_o_canal_na_porta_do_motorista` monta o canal a partir do bloco que a janela gravou exatamente para essa regra não envelhecer em silêncio.

#### Testar acesso: a pergunta de verdade, sem efeito colateral

O contrato ganhou `SmsTransportDriver.testar_acesso()`. Ele **não é abstrato de propósito**: o padrão devolve a saúde que a configuração diz, porque há meio que não tem o que conferir de fora (`loopback`) e meio que só saberia mentir — um envio de prova chegaria ao cliente. Quem tem teste honesto reimplementa:

- **`android_lan`** abre o soquete TCP no endereço que usaria para enviar, fecha sem empurrar um byte e devolve `<host>:<porta>`. Se o endereço fixo falhou e a descoberta está ligada, gira pela lista descoberta (limitada) antes de desistir; sem nenhum celular na rede, diz «nao apareceu na rede» sem ter tocado em porta nenhuma.
- **`smtp_email`** conecta e autentica na saída, dá `quit` sem escrever mensagem; e sonda a entrada **só se ela foi configurada** — IMAP com `login`/`logout` (nunca `SELECT`, `SEARCH` ou `FETCH`: ler a caixa da loja não é papel de um botão de teste) ou POP3 com `USER`/`PASS`/`QUIT`. As três respostas possíveis são «saída e entrada conferem», «a saida confere; a leitura esta desligada (falta o servidor de entrada)» e «a saida confere, mas a leitura falhou: <motivo>» — a saída boa não é escondida quando a entrada está errada, nem o contrário.

Três decisões de desenho valem registro:

- **reusa o motorista vivo.** Com a barra de pé, a pergunta vai ao objeto que a fila já usa (`registry.drivers()`), então PDV e HUB no mesmo celular batem no mesmo canal, uma pergunta depois da outra — nenhum segundo motorista é montado para a tela. Medido por contador: duas origens, duas chamadas, um motorista. Com a barra desligada, a tela monta um canal igualzinho a partir do arquivo (`construir`) para o lojista conferir **antes** de ligar nada; isso não liga a barra, não abre a fila e não toca na porta de comprovantes.
- **nunca derruba o painel.** O que estourar dentro da sonda vira `Health(False, "a verificacao nao terminou: …")`; um canal que não monta vira «nao deu para preparar o canal com os ajustes salvos» na tela e o motivo completo vai para o registro de eventos com o nome do canal.
- **roda fora da linha da interface**, e o resultado chega com hora e com o identificador que o motorista devolve — `14:32 Celular pela rede da loja: acesso conferido (192.168.0.9:49998)` ou `14:32 Caixa de e-mail da loja: acesso conferido (email:balcao@exemplo.com.br) - a saida confere; a leitura esta desligada (falta o servidor de entrada)`. No registro de eventos a mesma linha sai nomeada por origem (`Teste de acesso PDV (Caixa de e-mail da loja): …`), e é lá — não na tela — que vai o motivo técnico completo de um canal que não monta (`Canal 'usb_modem' nao montou para o teste: o motorista do modem USB ainda nao foi escrito`). O que o lojista lê antes do primeiro clique é o texto fixo da linha: «Nenhum teste de acesso ainda. Ele nao envia mensagem nenhuma a ninguem.»

#### Ligar, desligar e trocar de canal agora é decisão de tela — e a 1.7 acompanha

É aqui que esta onda afiou comportamento da 1.7, e não só acrescentou botões. Antes, só a leitura do arquivo na inicialização decidia quem ficava com o celular; com o painel decidindo, três caminhos novos precisavam existir:

| Ação na tela | O que acontece com a barra | O que acontece com a 1.7 |
| --- | --- | --- |
| Marcar **Ligar a barra de mensagens** | `enabled: true` no arquivo e `_start_messaging()` | se o canal escolhido for o celular, `_parar_envio_da_ponte()` + porta de comprovantes de pé |
| Desmarcar | `_stop_messaging()` | **`_devolver_a_ponte_antiga()`**: a ponte volta a enviar |
| Trocar o canal de uma origem | `_reiniciar_a_barra()` (relê o arquivo sem fechar o Gaspar) | volta para a 1.7 se o celular ficou livre; **não é tocada** se a troca não envolve o celular |

A regra de quem recebe o aparelho de volta é a mesma que a B6-5 afiou para a porta: **o sinal de que a ponte está cedida é o `base_url` do motorista dela** — quem cede limpa, quem recebe devolve. Isso evita o efeito colateral feio de reiniciar uma ponte que já estava de pé por uma troca que nada tem a ver com o celular (e-mail → ensaio, por exemplo), que é caso de teste próprio. Junto disso, `_start_sms_services()` passou a **reanexar** o `base_url` quando encontrou a porta já levantada pelos comprovantes, e `_soltar_porta_de_comprovantes()` desinstala os ganchos da 2.0 quando a 1.7 volta a mandar. São as duas pontas que faltavam para o ciclo fechar sem reiniciar o programa.

E uma decisão que custou duas linhas: **o que não foi para o disco não pode ficar na memória.** `_on_messaging_enabled`, `_on_meio_change` e `_salvar_meios` desfazem o modelo quando `save()` estoura (`OSError`, pasta protegida, disco cheio), reverteram a caixinha e param ali, com uma linha no registro do sistema. Sem isso, a tela mostrava «desligado» enquanto o config dizia `True` — e a próxima releitura diria o contrário da última frase dita ao lojista. **Emendado em 21/11/2026:** a janela dos ajustes tinha a regra só na palavra — ela aplicava os blocos na memória, via `set_settings`, e devolvia cedo quando o disco recusava, deixando o config com um canal que o `messaging.json` nega — e o primeiro salvamento que der certo depois disso leva o bloco fantasma para o arquivo, onde a fábrica montaria uma caixa postal que ninguém gravou). `_salvar_meios` agora guarda o bloco anterior de cada canal que tocou e devolve todos se a escrita falhar; a janela continua aberta, o texto digitado continua nos campos, e a prova é dupla: `test_a_janela_de_ajustes_que_nao_consegue_salvar_volta_atras` (memória igual a antes, sem linha de «salvos») e `test_a_janela_devolve_o_mapa_inteiro_sem_inventar_canal` (o mapa inteiro volta chave por chave, inclusive um canal que a janela não mostra). **Estado deste texto:** a emenda é da árvore local de 21/11/2026, ainda não versionada — na `master` `e314969` o bloco que o disco recusou continua ficando na memória (item D-2 da fila de polimento).

#### O que esta onda não é

- **Não migra o pareamento da 1.7.** O segredo (`shared_secret_b64`) e a chave pública do celular continuam no `sms_config.json`, e a janela dos ajustes **não lê o arquivo de outro produto** — decisão registrada, não esquecimento: a barra não escreve nem apaga pareamento, e enquanto o lojista não colar o segredo uma vez no campo **Segredo do pareamento** (ou gravar `segredo_sealed` pelo caminho manual), o canal do celular fica indisponível com o motivo dito. Uma onda própria, se o dono quiser o degrau automático.
- **Não prova entrega.** «Acesso conferido» quer dizer «dá para falar com o servidor/celular agora», não «o SMS chegou»: a entrega é o comprovante da B6-5.
- **Não inventou capacidade no motor.** Um motorista por tipo continua valendo — duas caixas postais diferentes para PDV e HUB seguem fora de escopo, e a tela reflete isso: os ajustes são **por canal**, não por origem.
- **Não encosta no 1.7.4 em produção.** O padrão de fábrica continua `enabled: false`: com o arquivo como está hoje, a aba nova mostra a barra desligada e nada monta, nenhuma porta abre.
- **Nenhum dos testes desta onda viu um aparelho ou uma caixa postal de verdade.** São 25 casos de painel com janela escondida, soquete e conexão de mentira: provam a tela, o arquivo e a decisão sobre a ponte — não provam que a loja consegue ligar a barra num balcão com celular pareado. Essa é a pendência de validação real que continua aberta, com nome, depois da B6.

**Medido no gate local** (Python 3.13, `GASPAR_HOME` em área de passagem): **714 testes OK** e 1 pulo, na árvore do lote (90,6 s) e reconfirmado no commit dele (98,0 s — o único número daqui que se move sozinho é o relógio da suíte em Windows), repositório em **84%** e `gaspar/messaging` em **94%** (2.561 sentenças, 148 delas fora da conta em Windows e 157 no Linux do Portão) contra o piso de 70% do Portão. Os módulos da sonda: `messaging/transport.py` **100%**, `transports/android_lan.py` **99%** (366 sentenças, eram 346), `transports/smtp_email.py` **91%**, `gaspar/app.py` **89%** (era 88%). Os 43 testes novos são 25 em `TelaDaBarraTests` (`tests/test_app.py`, que vai de 104 para 129), 10 em `SondaDeAcessoTeste` (`tests/test_messaging_email.py`), 6 em `TesteDeAcessoTeste` (`tests/test_messaging_lan.py`) e 2 em `tests/test_messaging_transport.py` — os dois últimos fecham o contrato da sonda padrão (quem não tem prova própria devolve a saúde do arquivo) e a resposta do `loopback`, que é a única frase de tela que não pode prometer mais do que «o arquivo diz isso».

**O Portão mediu a mesma onda no Linux.** O PR da onda (base `master`) fechou com `Portao pass` em cada ponta de documento que teve: `Ran 714 tests` em 47,6 s no commit `e4cba80` e em 44,9 s no commit `13181ba`, com `TOTAL 84%` — o relógio da suíte é o único número daqui que se move a cada push, e o que amarra o veredicto ao SHA enviado é o próprio Portão, não esta linha. Saiu também `OK (**skipped=2**)`, um pulo a mais que em Windows, diferença com nome: em `tests/test_messaging_store.py` dois casos de lista de permissões são `skipUnless(os.name == "nt")` e um de modo de arquivo é `skipIf(os.name == "nt")`, então a conta de pulos inverte entre as duas plataformas por construção. `gaspar/messaging` saiu em **94%** nos dois lados (148 sentenças de fora em Windows, 157 no Linux). As duas esteiras de pacote (`Pacote Linux`, `Pacote Windows`) não foram tocadas: o gatilho delas é etiqueta ou disparo manual, e o PR só acionou testes.

**D6:** nenhum módulo novo em `gaspar/messaging/` — os três métodos de sonda entraram em arquivos já listados nos specs, que continuam com **18** módulos, e o guardão `tests/test_packaging_manifest.py` segue verde.

**Uma fraqueza do próprio harness, achada e corrigida nesta onda.** As classes de painel abrem janelas próprias (Celular / SMS, QR, ajustes, registro de eventos) e o `tearDown` compartilhado destruía só a raiz: as janelas ficavam vivas, o coletor de lixo as encontrava depois do `root.destroy()` e o `__del__` das variáveis e imagens órfãs chamava um interpretador Tcl morto — `main thread is not in main loop`, `Tcl_AsyncDelete: async handler deleted by the wrong thread` e o processo **aborta sem imprimir o resumo da suíte** (código de saída 3: vermelho mudo, e com 93 linhas de ruído na classe nova). Com os 25 casos da tela isto deixou de ser teoria. Medido nesta árvore: a classe abortou **3 de 3** rodadas isolada; fechar a janela dos ajustes na limpeza da própria classe consertou a classe (**3/3 verde**) e **não** consertou o conjunto — a suíte completa abortou **2 de 2** execuções do gate com esse remendo dentro. A correção foi onde o defeito mora: `PainelBase._destruir()` agora destrói toda janela filha do app, larga a referência do app e roda `gc.collect()` **com o Tk vivo** antes de `root.destroy()`, o que vale para as quatro janelas e para qualquer teste de painel futuro; o remendo de classe foi apagado. Medido depois: classe 3/3, `tests.test_app` 4/4 com 129 OK e o gate de 714 acima duas vezes — **zero** linhas de ruído nas nove execuções (eram 31 na última passada vermelha do conjunto). Fica a lição em duas partes, porque a suíte tinha fechado verde em 713 testes com o vazamento já na árvore: **fechar o que abriu antes de destruir a raiz**, e o verde do conjunto inteiro não prova a saúde de uma classe isolada — a cronologia do coletor de lixo decide, e essa é a pior espécie de verde.

### Fila de polimento da Fase de Validação Real em bancada

Aberta pelo dono em 21/11/2026, no fechamento da Fase Beta na `master` (`e314969`, 714 testes). A fase que vem é a prova com aparelho físico, caixa postal de verdade e QR lido pela câmera — nada disso decidível por código. Nesta fila entram só as correções pequenas de comportamento que não mexem em contrato, porta, arquivo de estado nem na fila: o dono classificou as duas primeiras como **cosméticas**. Ela é também o endereço da «fila» a que o texto da B6-A se referia — as duas fraquezas da suíte em Windows (o caso do telefone offline que estoura o tempo e o `WinError 10053` do corpo grande, medido como herdado) continuam nela, sem correção autorizada.

| Item | Onde dói | O que fazer | Como está em 21/11/2026 |
| --- | --- | --- | --- |
| **D-1** | Aba **Celular / SMS**, botão **Pedido de teste** da 1.7 (`gaspar/app.py`, `_on_test_send`) | Consultar `_motivo_celular_reservado()` antes de enfileirar: com o celular cedido à barra 2.0, dizer isso na tela em vez de pôr o pedido na fila de uma ponte parada — ela enviaria sozinha quando a barra se desligasse, sem ninguém ter pedido de novo. | **Escrito e medido em árvore local, não versionada.** Duas provas em `CelularSmsTests`: com reserva nada chega à fila (`enviados == []`) e o aviso nomeia a barra; sem reserva o teste sai como sempre. A `master` `e314969` ainda enfileira sem avisar |
| **D-2** | Janela dos ajustes da barra (`gaspar/app.py`, `_salvar_meios`) | Se `config.save()` falhar, devolver o `transport_settings` ao que estava no arquivo, para a memória não carregar um canal que o disco recusou — no arranque seguinte a barra montaria o que o arquivo nega e a tela releria um ajuste que nunca foi salvo. | **Escrito e medido na mesma árvore local, não versionada.** Duas provas em `TelaDaBarraTests`: a janela volta atrás quando o disco recusa e devolve o mapa inteiro, sem inventar canal. A `master` `e314969` ainda deixa o ajuste fantasma na memória |

**Medida do lote local** (21/11/2026, Python 3.13, `GASPAR_HOME` em área de passagem): **718 testes OK** e 1 pulo, repositório em **84%**, `gaspar/app.py` em **89%** e `gaspar/messaging/convivencia.py` em **100%**. Os quatro casos novos são os dois de cada linha da tabela.

**Nada desta fila saiu da máquina.** Sem commit, sem push, sem etiqueta e sem release: 21/11/2026 é o dia em que os merges na `master` param, e o tronco continua limpo e verde nos seus 714 testes. Handoff envelhece — quem retomar a 2.0 re-medir a árvore antes de assumir que este lote local continua onde está. **Como o lote sobe (gravado pelo dono em 21/11/2026):** D-1 e D-2 não têm commit próprio — eles vão no mesmo empacotamento das provas de bancada (aparelho físico e caixa postal de verdade), porque a fase que os julga é a mesma que os mede.

**A próxima etapa, com nome (gravado pelo dono em 21/11/2026).** É a **validação de bancada**: um **aparelho físico** Android pareado pelo QR da loja e uma **caixa postal Gmail de verdade** na ponte de e-mail — sem emulador, sem soquete de mentira, sem caixa de teste. Ela é que fecha o único buraco de evidência que sobrou da Fase Beta: os 714 testes provam tela, arquivo e a decisão sobre a ponte; nenhum deles viu aparelho, chip, caixa postal real ou Wi-Fi de balcão; o pareamento e a caixa dependem de material que só o dono tem na mão (aparelho, número e caixa postal). **A bancada é o portão: nada se adianta antes dela.** Nem D-1 e D-2 desta fila, nem as outras aberturas registradas acima (o motorista `usb_modem` e a publicação do app Android 2.0 com etiqueta, release e canal). Quem retomar a 2.0 começa pela bancada, reporta o que mediu no aparelho e na caixa, e só depois volta a esta tabela.

#### O roteiro da bancada (gravado em 21/11/2026, antes de qualquer execução)

**Material que só o dono tem (nada disto é comprável por código).**

- Celular Android com chip físico e crédito, Android 7.0 ou mais novo (`minSdk 24` em `android/build.gradle:23`).
- **O pacote 2.0 não está publicado.** Releases param em `android-v1.7`; na árvore só existe o APK de teste `android/build/outputs/apk/debug/pdv-sms-enviar-2.0.apk`, assinado como depuração, porque a assinatura de release depende de `keystore.properties` que a máquina de build não tem (`android/build.gradle:34-50`). Consequência medida: instalar esse pacote por cima do 1.7 publicado exige desinstalar o 1.7 antes (certificados diferentes), **e desinstalar apaga o pareamento do aparelho**.
- O 1.7 publicado **já escuta a 49998** (`GatewayListenerService.java:39-40,125` está na etiqueta) mas **não tem a ponte de e-mail** — a varredura da etiqueta `android-v1.7` acha zero arquivos `Email*`/`Imap*`. Então a bancada do pilar e-mail depende do pacote local não publicado; a do pilar celular pode ser feita com o app que está no ar.
- Caixa **Gmail** da loja com **senha de aplicativo** (não a senha da conta). O código selo o que receber e aceita qualquer texto (`smtp_email.py:167`); gerar a senha de app é passo do painel do Google, fora do Gaspar.

**Passos no computador (dono).**

1. Aba **Celular / SMS**, quadro **Mensagens pelo computador (barra 2.0)**, botão **Ajustar celular e caixa de e-mail**.
2. No canal do celular: **Este canal esta ligado** e, em **Segredo do pareamento**, colar a chave que o pareamento já usa — ela **não migra sozinha** do `sms_config.json` da 1.7 (`app.py:112-126` são os campos; o selo sai por `app.py:1229-1236`). **Chave do celular (vem do pareamento)** é o outro lado do mesmo segredo.
3. Na caixa de e-mail: **Esta caixa de e-mail esta ligada**, **Conta da loja** (o Gmail da loja), **Senha de app da conta**, **Servidor de saida** `smtp.gmail.com` com **Porta de saida** `465` e cifra SSL, **Servidor de entrada (le a resposta do celular)** `imap.gmail.com` (`993`), **Caixa onde o pedido entra** vazia (= a própria conta) e **Chave da ponte** com a mesma base64 dos dois lados.
4. Botão **Testar acesso** antes de ligar nada: no e-mail ele autentica no SMTP e fecha a conversa, e só sonda a entrada se o host de entrada estiver preenchido; no celular ele abre e fecha o TCP sem enviar byte (`smtp_email.py:427-485`, `android_lan.py:290-316`).
5. Ligar a caixinha **Ligar a barra de mensagens** e escolher por origem: **CaraCore PDV envia por:** celular pelo Wi-Fi, **CaraCore Hub envia por:** caixa de e-mail. Na 1.7, o botão **Parear celular** gera o QR com o endereço do computador e o segredo (`app.py:526`, payload em `sms/config.py:141-158`) — vale 15 minutos.

**Passos no aparelho (dono).**

1. Instalar o pacote, aceitar **Permissões de SMS** e notificações, e ligar **Permitir envio de SMS** (`ConfigActivity.java:196-204`).
2. Conectar no Wi-Fi da loja pelo ajuste do próprio Android. O painel do Wi-Fi do app só guarda, mostra e gera QR da rede (`WifiQr.java:13`); ele **não** conecta ninguém.
3. Ler o QR de pareamento do computador (**Configurar com QR Code**) ou colar a chave e **Salvar e iniciar gateway** — é aqui que o aparelho aprende o endereço do computador (`ScanSetupActivity.java:49-54`).
4. **Abrir painel do e-mail**: **Endereço do e-mail da loja**, **Senha do aplicativo**, e em **Mais opções (endereço dos servidores)** o servidor de entrada com `993`, o de saída com `465` e a **Caixa onde o computador escreve** (`EmailActivity.java:59-65`, rótulos em `res/values/strings.xml:173-186`). Depois **Guardar** e **Testar agora**.
5. Ligar **Receber pedidos por e-mail** e deixar o serviço vivo: ele segura uma notificação contínua e o gateway se encerra sem pareamento (`EmailPonteServico.java:71-100`, `GatewayListenerService.java:59-62`); no reboot ele volta sozinho (`BootReceiver.java:18-21`).

**O que a bancada tem de provar, com a régua de cada prova.**

| Prova | Caminho real | Fecha quando |
| --- | --- | --- |
| SMS pelo celular da loja | fila 2.0 → TCP 49998 → `SmsManager` (`PhoneRadio.java:25-36`) → recibo em `POST /api/mobile/receipt` na porta 8766 | o pedido na fila muda para `enviado` e depois `entregue` por `gaspar/messaging/comprovantes.py`, com a origem vinda da fila e não do aparelho |
| SMS pela caixa Gmail | computador escreve `GASPAR <origem> <id>` com corpo cifrado → app lê por IMAP (`UID FETCH … BODY.PEEK[]`, sem apagar) → chip envia → recibo volta pelo mesmo e-mail | idem, e a caixa continua com os recados após a leitura |
| Precedência da 49998 | barra ligada: ponte 1.7 cede; barra desligada: 1.7 retoma | `503 celular_reservado` no `POST /api/sms` da 8766 com a barra ligada, `202` com ela desligada |
| Padrão de fábrica | perfil limpo em pasta de passagem | `messaging.json` nasce com `enabled: false`, nenhuma porta abre |

**O que a bancada não pode prometer (lacunas medidas hoje, antes de culpar o aparelho).**

- **O endereço de volta não é preenchido pelo caminho 2.0.** `base_url` existe no motorista (`android_lan.py:161`) e só vai no quadro se estiver cheio (`android_lan.py:371-372`), mas **não há campo na tela nem escritor no produto** — quem ensina o endereço ao celular hoje é o QR da 1.7 (`ScanSetupActivity.java:51`) ou o `base` do comando da ponte 1.7 (`app.py:717`, `sms/protocol.py:43-44`). Sem isso o comprovante não tem para onde voltar.
- **Nenhum programa do produto emite a credencial da API 8767.** `issue_credential` só tem chamada no script de auditoria `.auditoria/sonda_alpha.py:139-140`, arquivo não versionado. A bancada mede fila → meio → aparelho; o trecho PDV/Hub → fila ainda não existe no produto.
- **A sonda do e-mail é cega para a leitura quando falta o host de entrada** (`smtp_email.py:457-485`): «acesso conferido» aí quer dizer SMTP autenticou, nada mais.
- **O botão Pedido de teste do app não prova canal.** Ele cria um pedido local de origem `teste` (`ConfigActivity.java:375-390`) e a resposta nem chega ao computador (`ConfirmationResponder.java:23-25`).
- **Licença não é portão de envio no app:** nenhum caminho de envio chama `isLicencaValida()`, então «enviou com licença inativa» não é defeito novo.
- **No aparelho só existe IMAP** (zero POP3 em `EmailActivity`/`EmailBridge`), enquanto o computador tem reserva POP3. Se o Gmail fechar o IMAP, a bancada trava do lado do celular.
- `usb_modem` continua sem motorista.

**O que a bancada gasta de verdade.** SMS cobrado pelo chip (o app tem teto de 300 por dia e a barra tem cota por origem e por minuto), e-mails reais entrando na caixa do Gmail, e uma autenticação real no Google a cada **Testar agora** — se o campo for preenchido com a senha da conta em vez da senha de app, o bloqueio vem do provedor, não do Gaspar. Recomendação medida pelo desenho: usar o número do próprio operador como destinatário.

**A regra do portão, repetida de propósito:** nada acima se executa antes da palavra do dono, e nada se adianta depois desta tabela sem que a bancada tenha sido feita e reportada.

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

A fonte de publicação do Pages é **GitHub Actions**, então só essa esteira
escreve no site: uma alteração em `docs/` chega ao ar na próxima publicação do
canal, não a cada push. Antes dessa configuração, o Pages republicava a pasta
`docs/` do `master` sozinho em cada push e apagava o `latest.json` do ar até a
esteira do canal rodar de novo (medido em 12/11/2026).

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
  "version": "1.7.4",
  "downloadUrl": "https://github.com/.../GasparSetup-1.7.4.exe",
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
| `python tools/gaspar_channel.py monitor` | Confere o canal publicado (oficial e espelho) contra a release mais nova e os pacotes no ar; é o que a esteira agendada roda. |

A configuração do canal fica em `release/channel.json` (repositório, prefixo de
etiqueta, `key_id`, `min_supported`, `notes_url`, endereço do canal, endereço do
espelho e padrões de asset). A ferramenta importa `gaspar.updates`, então o
manifesto é provado com a mesma verificação que o aplicativo usa.

### Publicar uma versão

Uma vez só, com o HD removível conectado, gere o par de chaves:

```bash
python tools/gaspar_channel.py init-key --key C:/caminho/seguro/gaspar-signing.pem
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
   $env:GASPAR_RELEASE_SIGNING_KEY = Get-Content C:\caminho\seguro\gaspar-signing.pem -Raw
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
6. **Deixe a vigilância assumir:**

   ```bash
   python tools/gaspar_channel.py monitor
   ```

   Ele exige que o canal publicado seja o da release mais nova e que os pacotes
   continuem no ar com o tamanho declarado. Daí em diante a esteira
   `canal-monitor.yml` repete a checagem a cada 6 horas e falha alto se algo
   mudar.

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

O selo **Latest** da vitrine do GitHub é outro assunto: é um só por repositório.
A esteira do Android cria o rascunho com `--latest=false` para o celular não
herdar o destaque do Gaspar do computador. Mas `gh release edit`, que é como o
rascunho vira publicação, não tem a opção contrária — só `--latest`. Se uma
release Android sair com número maior que a do computador, confira o selo depois
de publicar e reponha:

```bash
gh release edit gaspar-vX.Y.Z --latest
```

O selo não interfere no canal de atualização nem na assinatura do manifesto; é
só o que o visitante vê primeiro na página de downloads.

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

Os 41 testes de `tests/test_updates.py` também usam apenas biblioteca padrão
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
- Canal com gateway principal e domínio antigo como reserva: ordem, reserva só
  quando o gateway falha, assinatura exigida nos dois, falha dupla com os dois
  endereços na mensagem e troca registrada uma vez no log.
- Monitor: canal saudável passa; espelho com outra versão, espelho assinado por
  outra chave, `key_id` inesperado, canal atrás da release e pacote com tamanho
  divergente são recusados; a etiqueta esperada dispensa consultar a release.

Os 12 testes de `tests/test_channel.py` provam a rotina de release sem rede e
sem chave real: espelho com bytes diferentes recusado, manifesto de outra
release recusado, `key_id` trocado recusado, canal atrasado sinalizado para
nova tentativa, versão adulterada recusada, regra de obrigatoriedade por
`min_supported` e conversão das etiquetas (`gaspar-v1.7.1`, `v1.6.0`;
`android-v1.3` é ignorada).

Os 2 testes de `tests/test_isolamento.py` falham se um domínio de pagamento ou
de nota fiscal (`api.mercadopago.com`, `api.plugnotas.com.br` e o sandbox)
aparecer na lista do BlackBox ou no código do pacote.

As ondas de 12/11/2026 fecharam o miolo sem tela, que antes não tinha teste:

- `tests/test_core.py` (45 testes): configuração, caminhos, log de eventos,
  bloco de telemetria no `hosts`, início automático, atividade (Windows e
  Linux), elevação do BlackBox e ajudantes do overlay.
- `tests/test_engine.py` (20 testes): ciclo de presença com backend falso
  (mouse, `F15`, Teams, sino, telemetria), adiamento por tela cheia e usuário
  ativo, trajeto do cursor e início/parada do motor.
- `tests/test_updates_extra.py` (29 testes): manifesto assinado contra um
  servidor HTTP local, download conferido, estado, roteiro PowerShell,
  abertura da página de notas e o monitor de canal.
- `tests/test_phone.py` (15 testes): cliente TCP contra um celular falso,
  descoberta UDP, escolha de endereço da rede e QR Code.
- `tests/test_app.py` (89 testes): painel de verdade, construído escondido com
  preferências numa pasta temporária. Cobre montagem da janela, intervalo,
  todas as opções, sobreposição, simulação, tela **Celular / SMS** (ponte,
  QR, envio de teste, apagar histórico, token), aviso de atualização (opcional,
  obrigatória, pular, adiar, download e falhas), registros, bandeja, BlackBox
  e saída. Sem display, a classe inteira é pulada; no Linux a esteira roda com
  `xvfb`.

Os testes de ponta a ponta abrem soquetes reais em `127.0.0.1`:

- `tests/test_e2e_sms.py` (6 testes): pedido assinado do PDV → servidor local →
  ponte → celular falso → envelope decifrado com a chave privada de teste →
  comprovante → `entregue`; celular offline falha sem bloquear a venda; saúde e
  token. Os três negativos: mensagem fora do modelo é recusada com `400` sem
  entrar na fila; nonce reaproveitado é recusado com `401` (`pedido repetido`);
  pedido vindo pelo endereço da rede local, e não pelo `127.0.0.1`, é recusado
  com `403`. Confere ainda que estado e auditoria não guardam número nem texto.
- `tests/test_e2e_update.py` (7 testes): manifesto Ed25519 servido por HTTP →
  consulta → download com SHA-256 → entrega ao instalador com o roteiro
  PowerShell decodificado; pacote adulterado não fica no disco; reserva
  responde quando o principal cai; `min_supported` obriga a atualização.

Cobertura medida em 12/11/2026 com `coverage` (327 testes unitários):

| Camada | Cobertura |
| --- | --- |
| Núcleo sem tela (`config`, `paths`, `eventlog`, `autostart`, `telemetry_hosts`) | 82–99% |
| Motor de presença (`presence`) | 89% |
| Canal de atualização (`updates`) | 94% |
| Ponte de SMS (`sms/`) | 78–100% |
| Painel (`app`) | 89% |
| Sobreposição e bandeja (`overlay`, `tray`) | 18–23% |
| **Total** | **77%** |

A sobreposição animada e a bandeja continuam cobertas só pelo teste de fumaça:
exigem janela visível e relógio real. A esteira roda
`coverage run --source=gaspar` — no Linux sob `xvfb` — e falha abaixo de 70%.

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

- Testes automáticos: **332 testes** — 327 unitários (89 do painel, 59 da ponte de SMS, 43 do canal, 29 de lacunas do canal, 45 do núcleo, 20 do motor, 15 de rede e QR, 12 da rotina de release, 6 de ponta a ponta da ponte, 7 de ponta a ponta do canal e 2 de isolamento) e 5 do teste de fumaça —, aprovados na árvore local em 12/11/2026 com cobertura de **77%**; a esteira `gaspar.yml` executa os 327 unitários no Windows e, no Linux, sob `xvfb`, com piso de cobertura de 70% e o teste de fumaça no Linux; a esteira da etiqueta 1.7.4 passou nos dois sistemas.
- Canal de atualização: **no ar**. O `latest.json` (3.344 bytes) da 1.7.4 foi assinado com a chave `gaspar-2026-11` e publicado na [Release 1.7.4](https://github.com/chmulato/caracore-mascote/releases/tag/gaspar-v1.7.4). Medido em 13/11/2026: o gateway `api.caracore.com.br/releases/gaspar/latest.json` e o domínio `gaspar.caracore.com.br/latest.json` entregam os mesmos 3.344 bytes, e a assinatura confere com a chave pública em `assets/gaspar-update-public.pem` (`key_id` `gaspar-2026-11`, `min_supported` 1.7.0). A chave privada fica só no HD removível do responsável; a pública está versionada e dentro dos dois pacotes. Desde a 1.7.2 o canal consulta o gateway primeiro e deixa o domínio antigo como reserva.
- Vigilância do canal: a esteira `canal-monitor.yml` roda a cada 6 horas e falha quando o canal sai do ar, perde a assinatura, diverge do espelho, fica atrás da release mais nova ou aponta para pacote ausente ou com tamanho diferente. O comando equivalente é `python tools/gaspar_channel.py monitor`; medido no ar e na esteira em 12/11/2026.
- Atualização real de ponta a ponta (baixar, instalar em silêncio e reabrir): **não concluída**. O roteiro PowerShell foi validado por análise sintática e, em seguida, disparado pelo app no sandbox — sem sucesso, pelos dois defeitos descritos abaixo. O ciclo 1.7.0 → 1.7.1 foi medido em 12/11/2026 como reinstalação manual por cima: versão final 1.7.1, preferências e token preservados, canal consultado no primeiro minuto e desinstalação limpa. O ciclo automático 1.7.1 → 1.7.2 foi medido no mesmo sandbox em 12/11/2026 e **falhou** por dois defeitos do atualizador: a pasta de download não era criada e o processo que instala era encerrado junto com o aplicativo. Os dois foram corrigidos na 1.7.3 e cobertos por teste (o teste novo falha no código antigo com o mesmo `FileNotFoundError` que o app registrou), mas o ciclo automático ainda não foi reexecutado.
- Janela **Celular / SMS**: validada no teste de fumaça com a ponte desligada; o pareamento real depende de um celular Android.
- Botão **Tirar o Gaspar da tela**: validado no teste de fumaça; o mascote some, o botão vira **Trazer o Gaspar de volta** e a simulação e a ponte continuam ativas.
- Envio real de SMS: **não executado** nesta máquina, porque depende de um celular Android pareado e de um chip com crédito. O protocolo foi validado contra o código do app Android em teste automatizado (mesma derivação de chave e mesmo formato de cifra).
- Pacotes 1.7.4: gerados pela esteira nos dois sistemas, com `SHA256SUMS.txt` conferido e publicado na Release 1.7.4 — instalador 31 MB, `.deb` 41 MB e AppImage 30 MB.
- A instalação dos pacotes 1.7.4 em Debian 12 não foi medida nesta versão; a última instalação medida (Debian 12, `.exe` empacotado e AppImage) foi a da 1.6.0, com a mesma receita de build (Inno Setup 6 na máquina de build).
- Aplicativo Android 1.4 (código 5): APK e AAB **assinados** gerados pela esteira e publicados na [Release Android 1.4](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.4) em 12/11/2026 — APK de 704 KB, com `SHA256SUMS.txt`; o APK não foi instalado em celular nesta máquina. Envia a chave pública e só aceita SMS de licença vindo do número oficial salvo na tela, o que o Gaspar 1.7.1 ou mais novo exige; o 1.2 só atende quem continua no Gaspar 1.7.0. Continua publicado, e quem já o tem pode instalar o 1.6 por cima.
- Provedor de licença do 1.4 **publicado**: está exportado e sem permissão de leitura, medido no APK baixado da release — qualquer aplicativo que consulte a authority lê os dados. A etiqueta `android-v1.4` é publicada e não se move, então o defeito não foi corrigido no lugar: a correção saiu na 1.5, que fixa `readPermission` `SMS_INTERNAL` no `LicencaContentProvider`.
- Aplicativo Android 1.5 (código 6): APK e AAB **assinados** gerados pela esteira e publicados na [Release Android 1.5](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.5) em 12/11/2026 — APK de 720.857 bytes (704 KB), AAB de 682.068 bytes e `SHA256SUMS.txt`; os três foram baixados sem autenticação (`200`) e o hash confere. Mesmo certificado do 1.4, então instala por cima sem perder o pareamento. Fecha o provedor de licença: com `readPermission` `SMS_INTERNAL`, nem o `adb shell content query` lê os dados. Medido com `aapt2 dump xmltree` no APK **publicado**: provedor com `exported=true`, `readPermission=br.com.caracore.pdv.sms.permission.SMS_INTERNAL`, `versionCode` 6 e `versionName` 1.5. Gate da árvore verde (lint, 8 testes de `LicenseSmsTest`, `assembleDebug`). O APK não foi instalado em celular nesta máquina.
- Aplicativo Android 1.6 (código 7): APK e AAB **assinados** pela esteira e publicados na [Release Android 1.6](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.6) em 13/11/2026 — APK de 2.099.052 bytes e AAB de 1.915.879 bytes, com `SHA256SUMS.txt`; os três baixados sem autenticação (`200`) e o hash confere. `apksigner verify` na esteira: esquema v2, certificado `CN=Christian Vladimir Uhdre Mulato, OU=Cara Core Informatica` (SHA-256 `c2f09b23…9ccb`), o mesmo do 1.5 — o APK de release instalou por cima do 1.5 publicado no emulador sem desinstalar. `aapt2 dump badging` no APK publicado: `versionCode=7`, `versionName=1.6` e ícone mapeado em `res/` (o 1.5 vinha com `icon=''`); o painel do emulador mostra o cabeçalho do Gaspar. Traz o painel do Wi‑Fi da loja (senha cifrada pelo Android Keystore, revelação/cópia/QR após biometria ou PIN, some em 30 s) e a confirmação de desconto/cancelamento/sangria pelo botão **Pedido de teste** — o Gaspar/PDV ainda não envia `confirmar_operacao`. Gate: 21 testes unitários e lint verdes; exercitado em emulador Android 13 (API 33), não em celular físico (SMS com chip, biometria de digital, tela bloqueada e QR pela câmera pendentes).
- Aplicativo Android 1.7 (código 8): APK e AAB **assinados** pela esteira e publicados na [Release Android 1.7](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.7) em 15/11/2026 — APK de 2.094.869 bytes (SHA-256 `aa67eba6…602a`) e AAB de 1.909.267 bytes (SHA-256 `006a41ce…cc4`), com `SHA256SUMS.txt`; os três baixados sem autenticação (`200`) e o hash confere. Certificado igual ao do 1.6, e o APK assinado instalou por cima do 1.6 publicado no emulador (código 7 → 8, alvo 27 → 35). Retira a leitura de SMS (licença digitada no painel ou pelo QR), não pede isenção da economia de bateria, exige token do PDV no aviso de backup e abre a confirmação só depois do toque na notificação. Gate local: build, 27 testes unitários (10 de confirmação, 3 de QR de Wi‑Fi, 8 da licença e 6 do token de backup) e lint verdes. O 1.6 e o 1.5 continuam publicados nas respectivas releases. Não exercitado em celular físico: SMS com chip, biometria de digital, notificação com tela bloqueada e QR pela câmera.
- Nenhum APK, keystore ou senha é versionado.
