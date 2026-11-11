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

No Linux, instale também `python3-tk`, `libx11-6`, `libxext6`, `libxtst6` e `libxss1`.

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
| `gaspar/telemetry_hosts.py` | Bloqueio de telemetria no arquivo `hosts`. |
| `gaspar/tray.py` | Ícone da bandeja. |

## Estrutura do repositório

```text
.
├── assets/
│   ├── gaspar.png                 # imagem oficial (512 px, transparência real)
│   ├── gaspar.ico                 # ícone 16..256 px
│   └── gaspar_flutuando.gif       # animação de flutuação (220x220)
├── docs/
│   ├── blackbox.md                # guia do ambiente black-box
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
│   └── smoke_test.py
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

## Testes

```bash
python tests/smoke_test.py
```

O teste de fumaça usa uma pasta temporária via `GASPAR_HOME`, não altera o `hosts` real e cobre:

- Persistência de configuração (incluindo modo discreto e pausa em tela cheia).
- Aplicação, idempotência e remoção do bloco de telemetria em um arquivo temporário.
- Leitura de ausência e detecção de tela cheia.
- Criação do painel e do overlay reais.
- No Windows: chave de cor `#ff00ff`, opacidade 82%, clareamento para 12% perto do cursor, `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_NOACTIVATE`, click-through e z-order abaixo do painel.
- Trajeto apenas entre cantos vizinhos, sem cruzar o centro.
- Sumiço e retorno durante tela cheia simulada.
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

- Testes de fumaça: aprovados no Windows.
- Build Windows com PyInstaller: aprovado para `gaspar.exe` e `gaspar_blackbox.exe`.
- Execução do `.exe` empacotado: validada em pasta de dados temporária.
- Instalador Inno Setup: script pronto; a compilação exige o Inno Setup 6 instalado na máquina de build.
- Pacotes Linux (`.deb`/AppImage): scripts prontos; a geração exige uma máquina Linux com `dpkg-deb` e, para AppImage, `appimagetool`.
