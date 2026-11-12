![Gaspar, o mascote da Cara Core](assets/gaspar.png)

# Gaspar - Mascote Cara Core

O mascote oficial da **Cara Core Informática**: um fantasminha verde-limão que
flutua no canto da tela, mantém o seu status ativo no Teams e no Slack e, de
quebra, leva até o celular os SMS pedidos pelo PDV.

Ele foi feito para ser **discreto**. Não abre janelas por cima do seu trabalho,
não rouba o foco do teclado, não bloqueia cliques e não mexe no mouse enquanto
você está usando o computador.

|  |  |
| --- | --- |
| Branch oficial | **master** |
| Versão publicada do Gaspar | **1.7.2** |
| Aplicativo do celular publicado | **1.5** |
| Download | [Release 1.7.2](https://github.com/chmulato/caracore-mascote/releases/tag/gaspar-v1.7.2) |
| Licença | **MIT** |
| Plataformas | **Windows 10/11** e **Linux (X11/XWayland)** |
| Empresa | **Cara Core Informática** |

> **O que você baixa hoje.** Os arquivos de instalação publicados são o Gaspar
> **1.7.2** e o aplicativo do celular **1.5**. O aplicativo **1.5**, que fecha
> o acesso de outros aplicativos aos dados de licença e completa a proteção do
> SMS, acompanha o Gaspar **1.7.1** ou mais novo; quem continua no Gaspar
> **1.7.0** fica com o aplicativo **1.2**. O que ainda está por vir está em
> [O que vem na próxima versão](#o-que-vem-na-próxima-versão).

## Se você só quer usar

> Vai usar também o SMS pelo celular? O passo a passo dos dois lados, com a
> lista de arquivos, está em [wiki.caracore.com.br/gaspar/instalacao.html](https://wiki.caracore.com.br/gaspar/instalacao.html).

### Baixar agora

Escolha o arquivo do sistema que você usa. O download começa ao clicar no link.

| Seu sistema | Arquivo | Baixar |
| --- | --- | --- |
| Windows 10 ou 11 | `GasparSetup-1.7.2.exe` (31 MB) | [Baixar para Windows](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.2/GasparSetup-1.7.2.exe) |
| Debian, Ubuntu, Mint e derivados | `gaspar_1.7.2_amd64.deb` (41 MB) | [Baixar o .deb](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.2/gaspar_1.7.2_amd64.deb) |
| Outras distribuições Linux | `Gaspar-1.7.2-amd64.AppImage` (30 MB) | [Baixar o AppImage](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.2/Gaspar-1.7.2-amd64.AppImage) |

Para o **celular**, baixe o aplicativo `pdv-sms-enviar-1.5-release.apk` (704 KB)
na [Release do aplicativo Android 1.5](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.5).
Ele acompanha o Gaspar 1.7.1 ou mais novo; o aplicativo 1.2 só atende quem
continua no Gaspar 1.7.0.

Todos os arquivos ficam na página da [Release 1.7.2](https://github.com/chmulato/caracore-mascote/releases/tag/gaspar-v1.7.2). O arquivo [SHA256SUMS.txt](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.2/SHA256SUMS.txt) serve para conferir se o download chegou completo; se você não sabe o que fazer com ele, pode ignorar.

### Windows

1. Baixe o arquivo `GasparSetup-1.7.2.exe` no link acima.
2. Dê dois cliques e siga o assistente: **Avançar**, **Instalar**, **Concluir**.
3. Abra o Gaspar pelo atalho da Área de Trabalho ou pelo menu Iniciar.
4. Na primeira vez, o painel de configuração abre junto. Ajuste o que quiser e
   clique em **Ocultar** para deixar só o mascote na tela.
5. Para encerrar de verdade, clique com o botão direito no ícone perto do
   relógio e escolha **Sair**.

Se o Windows exibir o aviso azul do SmartScreen, clique em **Mais informações**
e depois em **Executar assim mesmo**. O programa não é assinado digitalmente;
isso é esperado em programas distribuídos diretamente pela Cara Core.

### Linux - Debian, Ubuntu, Mint e derivados

1. Baixe o arquivo `gaspar_1.7.2_amd64.deb` no link acima.
2. Dê dois cliques e instale pelo aplicativo de pacotes, ou use o terminal:

   ```bash
   sudo apt install ./gaspar_1.7.2_amd64.deb
   ```

3. Abra **Gaspar** pelo menu de aplicativos, ou digite `gaspar` no terminal.
4. O **Gaspar BlackBox** aparece no mesmo menu.

### Linux - qualquer distribuição, sem instalar

1. Baixe o arquivo `Gaspar-1.7.2-amd64.AppImage` no link acima.
2. Clique com o botão direito, abra **Propriedades**, vá em **Permissões** e
   marque **Permitir executar**.
3. Dê dois cliques no arquivo.

> Quer outra versão ou conferir os checksums? Todas ficam na página de
> [Releases](https://github.com/chmulato/caracore-mascote/releases). Para gerar
> os instaladores a partir do código-fonte, veja o
> [guia técnico](manual-tecnico/tecnico.md).

> O Gaspar precisa de uma sessão **X11 ou XWayland**. Em Wayland puro, o mascote
> pode aparecer com um fundo quadrado e o clique pode não atravessar.

## O que é o Gaspar

O Gaspar é um companheiro de tela. Ele fica flutuando nos cantos, dá pequenas
voltas de vez em quando e, em paralelo, simula uma presença ativa para que o
Teams e o Slack não mostrem você como ausente.

O mascote é a parte visível. Atrás dele funciona a **ponte de SMS** que atende
o PDV. Você pode **tirar o mascote da tela** a qualquer momento sem desligar a
ponte nem a simulação.

O aplicativo também inclui o **Gaspar BlackBox**, uma ferramenta opcional para
bloquear domínios de telemetria no arquivo `hosts` do sistema.

## O que ele faz por você

- **Dá vida à tela:** o mascote flutua e se movimenta suavemente entre os
  cantos.
- **Mantém seu status ativo:** envia uma tecla neutra (F15 por padrão) e um
  pequeno toque de atividade para Teams e Slack.
- **Registra o que aconteceu:** cada ciclo fica em `cycle_log.txt`, na pasta de
  dados do usuário.
- **Respeita sua ausência:** só age depois de 60 segundos sem mouse ou teclado.
- **Bloqueia telemetria (opcional):** o BlackBox aplica e remove um bloco de
  domínios no arquivo `hosts`, de forma reversível.
- **Envia SMS pelo celular:** o PDV pede, o Gaspar entrega ao aplicativo
  Android e o celular dispara a mensagem.

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
| Consulta só o canal oficial | A partir da 1.7.1, o Gaspar pergunta ao canal oficial se há versão nova; nenhum dado seu, de venda ou de SMS é enviado. O SMS circula só na sua rede Wi-Fi. |
| Não mexe em outros sistemas | Ele não conversa com Mercado Pago, PlugNotas nem com o PDV; só recebe pedidos de SMS no próprio computador. |

## SMS pelo celular

O Gaspar também pode servir de ponte entre o PDV e um celular Android. O
funcionamento é simples:

1. O PDV pede o SMS ao Gaspar, no mesmo computador.
2. O Gaspar entrega o pedido ao celular pela rede Wi-Fi.
3. O celular dispara a mensagem pelo chip e avisa quando o chip aceitou e
   quando a operadora confirmou a entrega.

Na janela **Celular / SMS** você pareia o aparelho lendo um QR code, faz um
envio de teste e acompanha os últimos resultados, com a marca de **enviado** (o
chip aceitou) e **entregue** (a operadora confirmou).

O Gaspar **1.7.2** já recusa pedidos que não vêm do próprio computador, exige
que o pedido do PDV venha assinado e aplica limites de envio por número. A
proteção de ponta a ponta do texto depende do aplicativo **1.5** do celular,
que já está publicado: use o aplicativo **1.5** com o Gaspar **1.7.1** ou mais
novo, e o aplicativo **1.2** só com o Gaspar **1.7.0**.
Detalhes em
[wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html) e [wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html).

Para usar, você precisa de três coisas:

1. **O Gaspar instalado** no computador (passos acima).
2. **O aplicativo do celular instalado** (APK `pdv-sms-enviar-1.5-release.apk`,
   publicado na [Release do aplicativo](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.5);
   o guia de instalação mostra o passo a passo). No primeiro uso, toque em
   **Liberar o app da economia de bateria**.
3. **Celular e computador na mesma Wi-Fi**, com o Gaspar aberto.

Depois disso: abra **Celular / SMS**, marque **Ponte ativa**, clique em
**Parear celular** e leia o QR com o aplicativo do celular.

> A ponte de SMS está no Gaspar **1.7.2** e o envio exige o aplicativo Android
> **1.5**, já publicado. Instaladores 1.6.0 não têm a ponte; atualize os dois
> lados.

O passo a passo completo dos dois lados, com a lista de arquivos de instalação,
está em [wiki.caracore.com.br/gaspar/instalacao.html](https://wiki.caracore.com.br/gaspar/instalacao.html). O uso no dia a dia e os
limites estão em [wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html).

## Conhecendo o painel

O painel é rolável e se ajusta à altura da tela.

### Liga e desliga

| Controle | O que faz |
| --- | --- |
| **Ativar** / **Parar** | Começa ou interrompe os ciclos da simulação. |
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
| **Tirar o Gaspar da tela** | Remove o mascote da tela. A simulação e a ponte de SMS continuam funcionando. O botão vira **Trazer o Gaspar de volta**. |
| **Celular / SMS** | Abre a ponte de SMS: pareamento, teste e acompanhamento. |
| **BlackBox** | Abre a ferramenta opcional de bloqueio de telemetria. |
| **Abrir logs** | Abre os registros do Gaspar (Eventos e Sistema), com atalho para a pasta de dados. |
| **Sair** | Encerra o Gaspar de verdade. |

A área de **Status** mostra se a simulação está ativa, quanto falta para o
próximo ciclo e quantos ciclos já foram executados.

## O ícone perto do relógio

O ícone da bandeja oferece:

- **Abrir painel**
- **Simulação ativa** (marcado quando está rodando)
- **Gaspar flutuante** (marcado quando visível)
- **Sair**

Fechar o painel pelo botão da janela **não encerra o app**: ele continua na
bandeja, com o mascote na tela. Use **Sair** para encerrar de verdade.

## Onde ficam seus arquivos

| Sistema | Pasta |
| --- | --- |
| Windows | `%APPDATA%\CaraCore\Gaspar\` |
| Linux | `~/.config/caracore/gaspar/` |

Arquivos:

- `config.json`: suas preferências.
- `cycle_log.txt`: histórico dos ciclos.
- Arquivos que começam com `sms_`: configuração e histórico da ponte de SMS.

Configurações e logs ficam somente no seu computador. A partir da 1.7.1, o
Gaspar consulta apenas o canal oficial de atualização e não envia dados seus,
de venda ou de SMS. Não compartilhe a pasta de dados: ela guarda o token do
pareamento do celular.

## O que vem na próxima versão

O que ainda **não** está nos instaladores publicados:

- **Chamada automática do PDV:** o PDV pede a mensagem ao Gaspar ao fechar a
  venda. Hoje o envio parte do painel do Gaspar ou de quem integra o PDV.

O Gaspar **1.7.2** do computador já está publicado com o aviso de versão nova e
as proteções do pedido de SMS. Para atualizar, baixe o instalador novo na página
de [Releases](https://github.com/chmulato/caracore-mascote/releases) e execute
por cima: suas preferências são mantidas.

## Perguntas frequentes

**Ele vai mexer no meu mouse enquanto eu trabalho?**
Não. Com **Agir somente quando eu estiver ausente** marcado, ele espera 60
segundos sem mouse ou teclado. Mesmo quando age, o movimento é curto e o cursor
volta para onde estava.

**Ele aparece durante uma reunião, vídeo ou jogo?**
Não. Com **Pausar em tela cheia** marcado, o mascote se esconde e os ciclos
param enquanto a tela cheia estiver ativa.

**Como faço para ele sumir da tela?**
Clique em **Tirar o Gaspar da tela**. O mascote some, mas o app continua na
bandeja e a ponte de SMS segue funcionando. Para voltar, clique em **Trazer o
Gaspar de volta**. Você também pode desmarcar **Gaspar flutuante** ou escolher
**Sair** na bandeja para encerrar o app.

**O Gaspar usa a internet?**
A partir da 1.7.1, ele consulta apenas o canal oficial para saber se existe
versão nova; nenhum dado seu, de venda ou de SMS é enviado. O SMS circula só na
sua rede Wi-Fi.

**O Gaspar mexe nas conexões do Mercado Pago ou do PlugNotas?**
Não. O Gaspar não conversa com essas APIs, não intercepta o tráfego e não altera
proxy, DNS ou firewall. O BlackBox, quando você aplica, bloqueia só uma lista
fixa de domínios de telemetria da Microsoft; Mercado Pago e PlugNotas não estão
nela. Um teste automático do projeto impede que isso mude sem aviso.

**Preciso ser administrador?**
Para usar o mascote e a simulação, não. Somente o **BlackBox** pede elevação,
porque altera o arquivo `hosts` do sistema.

**O que é o BlackBox?**
É uma ferramenta opcional que bloqueia domínios de telemetria da Microsoft, do
VS Code/Cursor, do Azure e do Application Insights. O bloqueio é reversível, mas
pode impedir login na Microsoft e instalação de extensões enquanto estiver
ativo. Leia o guia completo em [wiki.caracore.com.br/gaspar/blackbox.html](https://wiki.caracore.com.br/gaspar/blackbox.html).

**Funciona no Linux?**
Sim, em sessões X11 ou XWayland. Em Wayland puro, o recorte do mascote e o
clique atravessando podem não funcionar.

**Por que o antivírus ou o SmartScreen reclamam?**
O executável não é assinado digitalmente. Se você recebeu o arquivo da Cara Core
ou compilou a partir deste repositório, pode liberar. Caso contrário, não
execute.

**Como o Gaspar se atualiza?**
A partir da 1.7.1, o Gaspar consulta o canal oficial, confere a assinatura
digital e mostra um aviso discreto quando há versão nova, com **Atualizar
agora**, **Depois**, **Pular esta versão** e **Ver novidades** — nada é
instalado sem a sua permissão. No Windows ele baixa o instalador, confere o
arquivo e instala; no Linux, o botão abre a página de download. Quem está na
1.7.0 instala a 1.7.2 uma vez, à mão. O passo a passo está em
[Atualização do Gaspar](https://gaspar.caracore.com.br/atualizacao.html).

**Como desinstalar?**
No Windows, use **Aplicativos instalados** e remova **Gaspar - Mascote Cara
Core**. No Linux com `.deb`, use `sudo apt remove gaspar`. No AppImage, basta
apagar o arquivo.

## Problemas comuns

**O mascote aparece com um quadrado de fundo no Linux**
A sessão não está em X11/XWayland. Entre numa sessão X11. Em Wayland puro o
recorte do mascote não funciona; o guia técnico explica os detalhes.

**O mouse se mexe enquanto eu trabalho**
Confirme que **Agir somente quando eu estiver ausente** está marcado. Se o
sistema não detectar sua ausência, aumente o intervalo ou desmarque
**Movimentar o mouse**.

**O mascote cobre o painel**
Feche e reabra o painel; o mascote volta para trás dele.

**O BlackBox não abre**
Use uma instalação completa: no Windows, o instalador inclui o Gaspar e o
BlackBox; no Linux, o `.deb` e o AppImage incluem os dois. O BlackBox também
aparece no menu iniciar e pode ser aberto por lá.

**O celular não aparece na janela Celular / SMS**
Confirme a Wi-Fi, o aplicativo aberto e a bateria otimizada desativada. O passo
a passo está em [wiki.caracore.com.br/gaspar/instalacao.html](https://wiki.caracore.com.br/gaspar/instalacao.html).

**Preciso de ajuda com algum erro**
Veja os guias de
[instalação](https://wiki.caracore.com.br/gaspar/instalacao.html),
[SMS](https://wiki.caracore.com.br/gaspar/sms.html) e
[BlackBox](https://wiki.caracore.com.br/gaspar/blackbox.html). Se o problema for
no funcionamento interno, o [guia técnico](manual-tecnico/tecnico.md) tem a seção
de solução de problemas.

## Documentação

- **Site oficial:** [gaspar.caracore.com.br](https://gaspar.caracore.com.br/)
- **Instalação completa (computador e celular):** [wiki.caracore.com.br/gaspar/instalacao.html](https://wiki.caracore.com.br/gaspar/instalacao.html)
- **SMS no dia a dia:** [wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html)
- **Segurança e privacidade do SMS:** [wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html)
- **Atualização do Gaspar:** [página oficial](https://gaspar.caracore.com.br/atualizacao.html)
- **BlackBox e telemetria:** [wiki.caracore.com.br/gaspar/blackbox.html](https://wiki.caracore.com.br/gaspar/blackbox.html)
- **Guia técnico (código, build, protocolo e testes):** [manual-tecnico/tecnico.md](manual-tecnico/tecnico.md)

Este README foi feito para quem instala e usa o Gaspar. As instruções de
código, compilação e empacotamento ficam no guia técnico.

## Para quem compila

O código deste repositório é o da versão **1.7.3**, que corrige a instalação
automática da atualização e **ainda não está publicada**; a **publicada** é a
1.7.2, que está nos instaladores para download. Para usar a ponte de SMS, o
celular também precisa do aplicativo **1.5** (pasta `android/`), que lê o pedido
cifrado e já está publicado. As
instruções estão em [manual-tecnico/tecnico.md](manual-tecnico/tecnico.md) e
[android/README.md](android/README.md).

## Licença e créditos

Distribuído sob a licença **MIT**. Consulte [LICENSE](LICENSE).

- **Cara Core Informática**
- Autor: Christian Vladimir Uhdre Mulato
- Campo Largo, Paraná - Brasil
- 2026

A marca, o nome Gaspar e os ativos visuais pertencem à Cara Core Informática. O
código pode ser reutilizado conforme a licença MIT.
