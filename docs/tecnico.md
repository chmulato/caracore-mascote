# Guia técnico do Gaspar

Documentação para quem mantém, compila ou audita o Gaspar. O guia do usuário está no [README](../README.md).

- Branch oficial: **master**
- Versão: **1.6.0**
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
| `gaspar/sms/bridge.py` | Regras de envio, limites, fila, repetição e deduplicação por venda. |
| `gaspar/sms/client.py` | Conexão TCP com o aplicativo Android e leitura do recibo. |
| `gaspar/sms/config.py` | Configuração da ponte, segredos, token da API e token de pareamento. |
| `gaspar/sms/crypto.py` | Derivação da chave compartilhada e AES-256-GCM. |
| `gaspar/sms/discovery.py` | Descoberta do celular na rede local (UDP). |
| `gaspar/sms/network.py` | Descoberta do IP local do computador. |
| `gaspar/sms/protocol.py` | Formato do anúncio, do comando e do enquadramento TCP. |
| `gaspar/sms/qr.py` | Geração do QR Code de pareamento. |
| `gaspar/sms/server.py` | API HTTP local para o PDV e recepção do diagnóstico do celular. |
| `gaspar/sms/store.py` | Fila, histórico e trilha dos envios, com número mascarado. |
| `gaspar/telemetry_hosts.py` | Bloqueio de telemetria no arquivo `hosts`. |
| `gaspar/tray.py` | Ícone da bandeja. |

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
│   └── gaspar_flutuando.gif       # animação de flutuação (220x220)
├── docs/
│   ├── blackbox.md                # guia do ambiente black-box
│   ├── instalacao.md              # instalação do Gaspar e do aplicativo do celular
│   ├── sms.md                     # guia da ponte de SMS
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
│   │   ├── bridge.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── crypto.py
│   │   ├── discovery.py
│   │   ├── network.py
│   │   ├── protocol.py
│   │   ├── qr.py
│   │   ├── server.py
│   │   └── store.py
│   ├── telemetry_hosts.py
│   └── tray.py
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
│   ├── smoke_test.py
│   └── test_sms.py                # 20 testes unitários da ponte
├── tools/
│   └── make_assets.py
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

1. A janela continua sem bordas e sempre visível.
2. Cada quadro do GIF gera uma máscara 1-bit com a silhueta do Gaspar.
3. A extensão Shape do X11 (`XShapeCombineMask`) recorta o retângulo de fundo.
4. `XShapeCombineRectangles` com região vazia faz os cliques atravessarem o mascote.
5. A opacidade é aplicada com `-alpha` do Tk.

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
- `dist/installer/GasparSetup-1.6.0.exe` (quando o Inno Setup está instalado)

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
- `dist/linux/gaspar_1.6.0_<arch>.deb`
- `dist/linux/Gaspar-1.6.0-<arch>.AppImage`

Instalação do `.deb`:

```bash
sudo apt install ./dist/linux/gaspar_1.6.0_amd64.deb
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
chmod +x dist/linux/Gaspar-1.6.0-x86_64.AppImage
./dist/linux/Gaspar-1.6.0-x86_64.AppImage
```

O AppImage inclui o Gaspar e o BlackBox. O botão **BlackBox** do painel encontra o executável na própria instalação.

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

- Abra pelo botão **BlackBox** no painel do Gaspar.
- Ou use o atalho **Gaspar BlackBox** no Windows/Linux.
- O programa pede elevação sozinho.

CLI:

```bash
python -m gaspar.telemetry_hosts --status
python -m gaspar.telemetry_hosts --dry-run
python -m gaspar.telemetry_hosts --remove
```

O `--dry-run` não altera o arquivo e não exige administrador.

Atenção: o bloqueio inclui domínios de login e marketplace da Microsoft (`login.microsoftonline.com`, `vscode.dev`, `marketplace.visualstudio.com`). Isso pode impedir autenticação ou instalação de extensões enquanto o bloqueio estiver ativo. O guia completo, com configurações de telemetria do VS Code/Cursor, extensões e firewall, está em [docs/blackbox.md](blackbox.md).

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

### Descoberta do celular (UDP)

- Porta 49999, com broadcast para `255.255.255.255` e para os endereços de broadcast das interfaces (via `psutil`).
- O Gaspar envia `CARACORE-PDV-DISCOVER`.
- O app responde `CARACORE-APK|<ip>|<porta>`; o Gaspar guarda o IP e a porta em `sms_config.json`.
- Se a descoberta falhar, o pareamento por QR continua sendo a via principal, porque o app também informa o endereço do Gaspar.

### Envio (TCP + AES-256-GCM)

- Porta 49998 no celular.
- Cada mensagem é um quadro: 4 bytes de tamanho em big-endian, seguidos do texto cifrado.
- O texto cifrado é `IV de 12 bytes + AESGCM(...)`, com tag de 128 bits.
- O conteúdo é o JSON `{"action":"send_sms","number":"...","message":"...","id":"...","ts":...}` em UTF-8.
- A chave é derivada do segredo do QR: decodifica o base64; se o resultado tiver menos de 32 bytes, aplica SHA-256; usa os primeiros 32 bytes. A mesma regra está em `gaspar/sms/crypto.py` e no `GatewayCrypto` do app Android.
- Depois de enviar, o Gaspar espera um recibo do celular por até alguns segundos. Recibo ausente não invalida o envio: o pedido fica como `enviado` sem confirmação (`confirmed: false`).

### API para o PDV

Escuta em `0.0.0.0:<porta_http>` (padrão 8766). Autenticação por `X-Api-Token` ou `Authorization: Bearer <token>`; a comparação usa `secrets.compare_digest`.

| Método e rota | Função |
| --- | --- |
| `GET /api/health` | Estado da ponte, sem token: `ok`, `phone_online` e quantidade pendente. |
| `POST /api/sms` | Enfileira um SMS. Corpo: `{"number","message","venda_id"}`. |
| `GET /api/sms` | Últimos 20 pedidos. |
| `GET /api/sms/<id>` | Um pedido pelo identificador. |
| `POST /api/mobile/diagnostic` | Recebe o diagnóstico do celular no pareamento (token de setup, não o token da API). |

Códigos de `POST /api/sms`: `202` aceito, `400` número/mensagem inválidos ou corpo malformado, `401` token ausente ou errado, `429` limite por minuto ou por dia, `507` fila cheia.

Exemplo de chamada do PDV:

```bash
curl -X POST "http://192.168.0.10:8766/api/sms" \
  -H "Content-Type: application/json" \
  -H "X-Api-Token: SEU_TOKEN" \
  -d '{"number":"5511999999999","message":"Venda 123 confirmada. Obrigado!","venda_id":"venda-123"}'
```

```json
{"ok": true, "id": "7f3c...", "status": "fila", "confirmed": false}
```

O PDV deve tratar `sem resposta`, `401`, `429` e `507` como "não enviado" e tentar de novo mais tarde; o `venda_id` impede duplicidade quando a nova tentativa acontece dentro de 24 horas. O diagnóstico do celular usa `POST /api/mobile/diagnostic` com `token`, `sms_ok`, `battery_ok` e `message`; esse token é o de pareamento, não o da API, e é apagado depois do primeiro uso.

### Regras de segurança e de custo

- Número normalizado entre 10 e 15 dígitos, com `+` opcional; mensagem limitada a 480 caracteres.
- `venda_id` é idempotente por 24 horas: repetir a mesma venda devolve o pedido já existente em vez de mandar outro SMS.
- Limites padrão: 20 pedidos por minuto e 300 por dia; fila máxima de 100 pedidos.
- No máximo duas tentativas por pedido. Celular offline gera `falhou` com o motivo, sem repetir para sempre.
- Ao abrir, pedidos `fila` voltam para a fila; pedidos `enviando` viram `falhou` com "envio interrompido ao fechar o Gaspar", para não arriscar cobrança duplicada.
- Os logs mascaram o número; `sms_config.json` é gravado com permissão restrita (quando o sistema permite).
- O token da API e a chave compartilhada só existem no computador do lojista. Nenhum segredo é versionado no repositório.

### Arquivos da ponte

| Arquivo | Conteúdo |
| --- | --- |
| `sms_config.json` | Estado, porta, token da API, chave compartilhada, celular pareado e limites. |
| `sms_state.json` | Até 500 pedidos, com status e recibo. |
| `sms_log.jsonl` | Trilha de uma linha por mudança de status, com o número mascarado. |

Todos ficam na pasta de dados do usuário (`data_dir()`), respeitando `GASPAR_HOME`. O guia do usuário e o passo a passo do celular estão em [docs/sms.md](sms.md).

## Testes

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python tests/smoke_test.py
```

Os 20 testes unitários de `tests/test_sms.py` usam apenas biblioteca padrão (mais `cryptography`) e não abrem porta fixa nem acessam a internet. Eles cobrem:

- Configuração, geração e persistência dos segredos, token de setup de uso único e validade de 15 minutos.
- Derivação de chave quando o segredo tem menos de 32 bytes.
- Cifra e decifra no formato do app Android, incluindo detecção de adulteração.
- Enquadramento TCP, montagem do comando e leitura do anúncio de descoberta.
- Normalização de número e de mensagem, com recusa de entradas inválidas.
- Persistência, deduplicação por `venda_id` e restauração da fila.
- Envio com sucesso, repetição com celular offline, falha definitiva, limite por minuto e fila cheia.
- API local: saúde, autenticação, aceite, consulta por id, pedido inexistente e diagnóstico de uso único.

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

**O BlackBox não abre pelo painel**

Gere o build completo (Gaspar e BlackBox). No Windows, o instalador inclui os dois; no Linux, o `.deb` e o AppImage incluem os dois.

**Antivírus ou SmartScreen bloqueia o `.exe`**

O executável não é assinado. Adicione uma exceção somente se você confia na origem e compilou a partir deste repositório.

**Nada é registrado no log**

Verifique a pasta de dados do usuário e a permissão de escrita. Em testes, defina `GASPAR_HOME` para uma pasta temporária.

**O Windows pede permissão de firewall ao ligar a ponte de SMS**

É esperado: a API precisa aceitar conexões na rede local para o PDV e o celular. Autorize somente em redes privadas. Se a porta 8766 estiver ocupada, o Gaspar avisa no registro da ponte; troque a porta na janela **Celular / SMS**.

**O celular não aparece em Procurar celular**

Confirme que o celular e o computador estão na mesma rede Wi-Fi, que o aplicativo Android está aberto e que a rede não isola os dispositivos (redes de visitante costumam bloquear). O pareamento por QR funciona mesmo sem a descoberta. Mais casos em [docs/sms.md](sms.md).

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
| `BLACKBOX_AMBIENTE_DESENVOLVIMENTO.txt` | `docs/blackbox.md` |

## Regenerar os ativos

Os ativos oficiais podem ser regenerados a partir da arte original em fundo magenta:

```bash
python tools/make_assets.py caminho/para/gaspar_original.png
```

O script remove o magenta, recorta o mascote, suaviza a borda, desconta a franja magenta e grava PNG, ICO e GIF em `assets/`.

## Estado de validação desta versão

- Testes de fumaça: aprovados no Windows, com pasta de dados temporária.
- Ponte de SMS: 20 testes unitários aprovados; janela **Celular / SMS** validada no teste de fumaça com a ponte desligada.
- Botão **Tirar o Gaspar da tela**: validado no teste de fumaça; o mascote some, o botão vira **Trazer o Gaspar de volta** e a simulação e a ponte continuam ativas.
- Envio real de SMS: **não executado** nesta máquina, porque depende de um celular Android pareado e de um chip com crédito. O protocolo foi validado contra o código do app Android em teste automatizado (mesma derivação de chave e mesmo formato de cifra).
- Build Windows com PyInstaller: aprovado para `gaspar.exe` e `gaspar_blackbox.exe` **antes** da ponte de SMS; `gaspar.exe --version` respondeu `Gaspar 1.6.0`.
- Execução do `.exe` empacotado: validada em pasta de dados temporária.
- Instalador Inno Setup: `GasparSetup-1.6.0.exe` gerado (63 MB); a compilação exige o Inno Setup 6 instalado na máquina de build.
- Pacote `.deb`: instalado em Debian 12; `gaspar --version` respondeu `Gaspar 1.6.0` e as entradas de menu foram criadas.
- AppImage: executado com extração temporária; `gaspar --version` respondeu `Gaspar 1.6.0`.
- Os três instaladores e o `SHA256SUMS.txt` estão publicados na [Release 1.6.0](https://github.com/chmulato/caracore-mascote/releases/tag/v1.6.0), mas **não incluem** a ponte de SMS; um novo build é necessário para empacotá-la.
- Aplicativo Android: código-fonte versionado; o APK/AAB é gerado na máquina de build com JDK 11+, Android SDK e `adb`. Nenhum APK, keystore ou senha é versionado.
