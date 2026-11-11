![Gaspar, o mascote da Cara Core](assets/gaspar.png)

# Gaspar - Mascote Cara Core

O mascote oficial da **Cara Core Informática**: um fantasminha verde-limão que flutua no canto da tela, mantém seu status ativo no Teams e no Slack e não atrapalha o seu trabalho.

|  |  |
| --- | --- |
| Branch oficial | **master** |
| Versão atual | **1.6.0** |
| Download | [Release 1.6.0](https://github.com/chmulato/caracore-mascote/releases/tag/v1.6.0) |
| Licença | **MIT** |
| Plataformas | **Windows 10/11** e **Linux (X11/XWayland)** |
| Empresa | **Cara Core Informática** |

## Se você só quer usar

### Baixar agora

Escolha o arquivo do sistema que você usa. O download começa ao clicar no link.

| Seu sistema | Arquivo | Baixar |
| --- | --- | --- |
| Windows 10 ou 11 | `GasparSetup-1.6.0.exe` (63 MB) | [Baixar para Windows](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/GasparSetup-1.6.0.exe) |
| Debian, Ubuntu, Mint e derivados | `gaspar_1.6.0_amd64.deb` (33 MB) | [Baixar o .deb](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/gaspar_1.6.0_amd64.deb) |
| Outras distribuições Linux | `Gaspar-1.6.0-amd64.AppImage` (24 MB) | [Baixar o AppImage](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/Gaspar-1.6.0-amd64.AppImage) |

Todos os arquivos ficam na página da [Release 1.6.0](https://github.com/chmulato/caracore-mascote/releases/tag/v1.6.0). O arquivo [SHA256SUMS.txt](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/SHA256SUMS.txt) serve para conferir se o download chegou completo; se você não sabe o que fazer com ele, pode ignorar.

### Windows

1. Baixe o arquivo `GasparSetup-1.6.0.exe` no link acima.
2. Dê dois cliques e siga o assistente: **Avançar**, **Instalar**, **Concluir**.
3. Abra o Gaspar pelo atalho da Área de Trabalho ou pelo menu Iniciar.
4. Na primeira vez, o painel de configuração abre junto. Ajuste o que quiser e clique em **Ocultar** para deixar só o mascote na tela.
5. Para encerrar de verdade, clique com o botão direito no ícone perto do relógio e escolha **Sair**.

Se o Windows exibir o aviso azul do SmartScreen, clique em **Mais informações** e depois em **Executar assim mesmo**. O programa não é assinado digitalmente; isso é esperado em programas distribuídos diretamente pela Cara Core.

### Linux - Debian, Ubuntu, Mint e derivados

1. Baixe o arquivo `gaspar_1.6.0_amd64.deb` no link acima.
2. Dê dois cliques e instale pelo aplicativo de pacotes, ou use o terminal:

   ```bash
   sudo apt install ./gaspar_1.6.0_amd64.deb
   ```

3. Abra **Gaspar** pelo menu de aplicativos, ou digite `gaspar` no terminal.
4. O **Gaspar BlackBox** aparece no mesmo menu.

### Linux - qualquer distribuição, sem instalar

1. Baixe o arquivo `Gaspar-1.6.0-amd64.AppImage` no link acima.
2. Clique com o botão direito, abra **Propriedades**, vá em **Permissões** e marque **Permitir executar**.
3. Dê dois cliques no arquivo.

> Quer outra versão ou conferir os checksums? Todas ficam na página de [Releases](https://github.com/chmulato/caracore-mascote/releases). Para gerar os instaladores a partir do código-fonte, veja **Para quem é técnico**, mais abaixo.

> O Gaspar precisa de uma sessão **X11 ou XWayland**. Em Wayland puro, o mascote pode aparecer com um fundo quadrado e o clique pode não atravessar.

## O que é o Gaspar

O Gaspar é um companheiro de tela. Ele fica flutuando nos cantos, dá pequenas voltas de vez em quando e, em paralelo, simula uma presença ativa para que o Teams e o Slack não mostrem você como ausente.

Ele foi feito para ser **discreto**: não abre janelas por cima do seu trabalho, não rouba o foco do teclado, não bloqueia cliques e não mexe no mouse enquanto você está usando o computador.

O aplicativo também inclui o **Gaspar BlackBox**, uma ferramenta opcional para bloquear domínios de telemetria no arquivo `hosts` do sistema.

## O que ele faz por você

- **Dá vida à tela:** o mascote flutua e se movimenta suavemente entre os cantos.
- **Mantém seu status ativo:** envia uma tecla neutra (F15 por padrão) e um pequeno toque de atividade para Teams e Slack.
- **Registra o que aconteceu:** cada ciclo fica em `cycle_log.txt`, na pasta de dados do usuário.
- **Respeita sua ausência:** só age depois de 60 segundos sem mouse ou teclado.
- **Bloqueia telemetria (opcional):** o BlackBox aplica e remove um bloco de domínios no arquivo `hosts`, de forma reversível.

## O que ele não faz

| Proteção | O que isso significa no dia a dia |
| --- | --- |
| Não rouba o foco | Você continua digitando na janela em que estava; o Gaspar não assume o teclado. |
| Não bloqueia cliques | Clicar na área do mascote atravessa para o que está atrás dele. |
| Não atrapalha quem está trabalhando | Ele espera você ficar ausente antes de agir. |
| Não mexe no seu mouse | Quando age, faz movimentos curtos e devolve o cursor ao lugar original. |
| Não cobre o painel | Enquanto a janela de configuração está aberta, o mascote fica atrás dela. |
| Não aparece em tela cheia | Em vídeos, jogos e apresentações, ele se esconde e os ciclos pausam. |
| Não torna a tela ilegível | A opacidade padrão é 82%, e ele fica quase transparente quando o cursor se aproxima. |
| Não some sem aviso | Ao fechar o painel, ele continua na bandeja; só sai quando você escolhe **Sair**. |

## Conhecendo o painel

O painel é rolável e se ajusta à altura da tela.

### Liga e desliga

| Controle | O que faz |
| --- | --- |
| **Iniciar simulação ao abrir** | Começa os ciclos automaticamente quando o app abre. |
| **Movimentar o mouse** | Liga ou desliga o deslocamento suave do cursor. |
| **Sinal sonoro** | Toca um som ao final do ciclo. Vem desligado. |
| **Gaspar flutuante** | Mostra ou esconde o mascote. |
| **Manter Teams/Slack ativo** | Além da tecla, envia um pequeno toque de atividade. |
| **Iniciar com o sistema** | Abre o Gaspar junto com o Windows ou com a sessão Linux, já minimizado. |

### Discrição

| Controle | O que faz |
| --- | --- |
| **Agir somente quando eu estiver ausente** | Recomendado. Espera 60 segundos sem mouse ou teclado antes de executar um ciclo. |
| **Pausar em tela cheia** | Esconde o mascote e suspende os ciclos em vídeos, jogos e apresentações. |
| **Intervalo** | Tempo entre um ciclo e outro. Vai de 10 segundos a 1 hora. |
| **Tecla** | F15 (recomendada), Shift, Espaço ou Nenhuma. |
| **Opacidade do Gaspar** | De 50% a 100%. O padrão 82% dá o efeito translúcido; a faixa recomendada é 75% a 85%. |

### Botões

| Botão | O que faz |
| --- | --- |
| **Ocultar** | Esconde o painel e deixa o app na bandeja. |
| **BlackBox** | Abre o bloqueio de telemetria. |
| **Abrir logs** | Abre a pasta onde ficam as configurações e o histórico. |
| **Sair** | Encerra o Gaspar de verdade. |

A área de **Status** mostra se a simulação está ativa, quanto falta para o próximo ciclo e quantos ciclos já foram executados.

## O ícone perto do relógio

O ícone da bandeja oferece:

- **Abrir painel**
- **Simulação ativa** (marcado quando está rodando)
- **Gaspar flutuante** (marcado quando visível)
- **Sair**

Fechar o painel pelo botão da janela **não encerra o app**: ele continua na bandeja, com o mascote na tela. Use **Sair** para encerrar de verdade.

## Onde ficam seus arquivos

| Sistema | Pasta |
| --- | --- |
| Windows | `%APPDATA%\CaraCore\Gaspar\` |
| Linux | `~/.config/caracore/gaspar/` |
| Testes ou modo portátil | pasta indicada pela variável `GASPAR_HOME` |

Arquivos:

- `config.json`: suas preferências.
- `cycle_log.txt`: eventos e ciclos. Ao passar de 1 MB, o arquivo é rotacionado para `cycle_log.txt.1`.

Nada é enviado para a internet. Configurações e logs ficam somente no seu computador.

## Perguntas frequentes

**Ele vai mexer no meu mouse enquanto eu trabalho?**
Não. Com **Agir somente quando eu estiver ausente** marcado, ele espera 60 segundos sem mouse ou teclado. Mesmo quando age, o movimento é curto e o cursor volta para onde estava.

**Ele aparece durante uma reunião, vídeo ou jogo?**
Não. Com **Pausar em tela cheia** marcado, o mascote se esconde e os ciclos param enquanto a tela cheia estiver ativa.

**Como faço para ele sumir da tela?**
Desmarque **Gaspar flutuante**, clique em **Ocultar** para esconder o painel ou escolha **Sair** na bandeja para encerrar o app.

**Preciso ser administrador?**
Para usar o mascote e a simulação, não. Somente o **BlackBox** pede elevação, porque altera o arquivo `hosts` do sistema.

**O que é o BlackBox?**
É uma ferramenta opcional que bloqueia domínios de telemetria da Microsoft, do VS Code/Cursor, do Azure e do Application Insights. O bloqueio é reversível, mas pode impedir login na Microsoft e instalação de extensões enquanto estiver ativo. Leia o guia completo em [docs/blackbox.md](docs/blackbox.md).

**Funciona no Linux?**
Sim, em sessões X11 ou XWayland. Em Wayland puro, o recorte do mascote e o clique atravessando podem não funcionar.

**Por que o antivírus ou o SmartScreen reclamam?**
O executável não é assinado digitalmente. Se você recebeu o arquivo da Cara Core ou compilou a partir deste repositório, pode liberar. Caso contrário, não execute.

**Como desinstalar?**
No Windows, use **Aplicativos instalados** e remova **Gaspar - Mascote Cara Core**. No Linux com `.deb`, use `sudo apt remove gaspar`. No AppImage, basta apagar o arquivo.

## Problemas comuns

**O mascote aparece com um quadrado de fundo no Linux**
A sessão não está em X11/XWayland, ou faltam as bibliotecas `libX11` e `libXext`. Entre numa sessão X11 ou instale as bibliotecas.

**O mouse se mexe enquanto eu trabalho**
Confirme que **Agir somente quando eu estiver ausente** está marcado. Em sistemas sem detecção de ausência, aumente o intervalo ou desmarque **Movimentar o mouse**.

**O mascote cobre o painel**
Feche e reabra o painel; a ordem das janelas é reaplicada a cada meio segundo.

**O BlackBox não abre pelo painel**
Use uma instalação completa: no Windows, o instalador inclui o Gaspar e o BlackBox; no Linux, o `.deb` e o AppImage incluem os dois.

**Nada é registrado no log**
Verifique a pasta de dados do usuário e a permissão de escrita. Em testes, defina `GASPAR_HOME` para uma pasta temporária.

## Para quem é técnico

O Gaspar é escrito em **Python 3.10+** com **Tkinter**, **Pillow**, **pyautogui**, **psutil** e **pystray**.

### Rodar a partir do código

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
python run.py
```

Opções de linha de comando:

```bash
python run.py --minimized    # abre direto na bandeja
python run.py --version      # mostra a versão
python -m gaspar             # equivalente a run.py
python run_blackbox.py       # abre o BlackBox diretamente
```

### Testes

```bash
python tests/smoke_test.py
```

O teste usa uma pasta temporária via `GASPAR_HOME`, não altera o `hosts` real e cobre configuração, hosts, motor de presença, overlay, transparência, click-through, z-order, tela cheia e criação do log.

### Build

```bat
python packaging\windows\build_windows.py
```

```bash
bash packaging/linux/build_linux.sh
```

- Windows: `dist/windows/gaspar/gaspar.exe` e `dist/windows/gaspar_blackbox/gaspar_blackbox.exe`; o instalador Inno Setup exige o Inno Setup 6 instalado.
- Linux: `dist/linux/gaspar/gaspar`, `dist/linux/gaspar_blackbox/gaspar_blackbox`, além de `.deb` e AppImage quando `dpkg-deb` e `appimagetool` estiverem disponíveis.

Os executáveis não são assinados digitalmente. O SmartScreen pode avisar na primeira execução; isso é esperado em programas distribuídos diretamente pela Cara Core.

### Documentação técnica

- Estrutura completa, transparência, click-through, empacotamento, migração da versão antiga e estado de validação: [docs/tecnico.md](docs/tecnico.md).
- Blackbox, telemetria do VS Code/Cursor, extensões e firewall: [docs/blackbox.md](docs/blackbox.md).

### Estado de validação desta versão

- Testes de fumaça: aprovados no Windows, com pasta de dados temporária.
- Build Windows com PyInstaller: `gaspar.exe` e `gaspar_blackbox.exe` gerados; `gaspar.exe --version` respondeu `Gaspar 1.6.0`.
- Instalador Inno Setup: `GasparSetup-1.6.0.exe` gerado (63 MB).
- Pacote `.deb`: instalado em Debian 12; `gaspar --version` respondeu `Gaspar 1.6.0` e as entradas de menu foram criadas.
- AppImage: executado com extração temporária; `gaspar --version` respondeu `Gaspar 1.6.0`.
- Os três instaladores e o `SHA256SUMS.txt` estão publicados na [Release 1.6.0](https://github.com/chmulato/caracore-mascote/releases/tag/v1.6.0).

## Licença e créditos

Distribuído sob a licença **MIT**. Consulte [LICENSE](LICENSE).

- **Cara Core Informática**
- Autor: Christian Vladimir Uhdre Mulato
- Campo Largo, Paraná - Brasil
- 2026

A marca, o nome Gaspar e os ativos visuais pertencem à Cara Core Informática. O código pode ser reutilizado conforme a licença MIT.
