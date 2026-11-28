<p align="center">
  <img src="assets/gaspar.png" alt="Gaspar, o mascote da Cara Core">
</p>

# Gaspar - Mascote Cara Core

O mascote oficial da **Cara Core Informática**: um fantasminha verde-limão que
flutua no canto da tela, pode manter o seu status ativo no Teams e no Slack quando
você liga a simulação, e leva até o celular os SMS pedidos pelo PDV.

Ele foi feito para ser **discreto**. Não abre janelas por cima do seu trabalho,
não rouba o foco do teclado, não bloqueia cliques e não mexe no mouse enquanto
você está usando o computador.

|  |  |
| --- | --- |
| Branch oficial | **master** |
| Versão publicada do Gaspar | **1.7.4** |
| Aplicativo do celular publicado | **1.7** |
| Download | [Release 1.7.4](https://github.com/chmulato/caracore-mascote/releases/tag/gaspar-v1.7.4) |
| Licença | **MIT** |
| Plataformas | **Windows 10/11** e **Linux** |
| Empresa | **Cara Core Informática** |

## O que você baixa hoje

Está publicado e funcionando agora:

- **Gaspar 1.7.4** no computador — Windows, Linux e a versão que roda sem
  instalar nada.
- **Aplicativo do celular 1.7** — o Gaspar aparece no aparelho, mostra o painel
  do Wi-Fi da loja e deixa você confirmar uma operação do PDV na tela do
  celular. A licença é digitada por você, o app não lê suas mensagens, não pede
  liberação da economia de bateria e a confirmação só abre quando você toca no
  aviso.

O aplicativo **1.7** acompanha o Gaspar **1.7.1** ou mais novo. Quem ainda está
no Gaspar **1.7.0** usa o aplicativo **1.2**. O que ainda não saiu fica em
**O que vem na próxima versão**, mais abaixo.

## Baixar

Escolha o arquivo do sistema que você usa. O download começa ao clicar no link.

| Seu sistema | Arquivo | Baixar |
| --- | --- | --- |
| Windows 10 ou 11 | `GasparSetup-1.7.4.exe` (31 MB) | [Baixar para Windows](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.4/GasparSetup-1.7.4.exe) |
| Debian, Ubuntu, Mint e derivados | `gaspar_1.7.4_amd64.deb` (41 MB) | [Baixar para Linux](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.4/gaspar_1.7.4_amd64.deb) |
| Qualquer outra distribuição Linux | `Gaspar-1.7.4-amd64.AppImage` (30 MB) | [Baixar a versão sem instalar](https://github.com/chmulato/caracore-mascote/releases/download/gaspar-v1.7.4/Gaspar-1.7.4-amd64.AppImage) |
| Celular Android | Aplicativo **1.7** (2,0 MB) | [Baixar para o celular](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.7) |

Todas as versões ficam na página da
[Release 1.7.4](https://github.com/chmulato/caracore-mascote/releases/tag/gaspar-v1.7.4).
A página também traz a lista de conferência dos arquivos: se você não precisa
conferir um download, pode ignorá-la.

## Instalar

### Windows

1. Baixe o instalador e dê dois cliques: **Avançar**, **Instalar**, **Concluir**.
2. Abra o Gaspar pelo atalho da Área de Trabalho ou pelo menu Iniciar.
3. Na primeira vez, o painel de configuração abre junto. Ajuste o que quiser e
   clique em **Ocultar** para deixar só o mascote na tela.
4. Para encerrar de verdade, clique com o botão direito no ícone perto do
   relógio e escolha **Sair**.

Se o Windows mostrar o aviso azul, clique em **Mais informações** e depois em
**Executar assim mesmo**. É esperado: o programa vem direto da Cara Core, sem o
selo pago de editor que a Microsoft costuma exigir de quem distribui por fora.

### Linux com gerenciador de pacotes (Debian, Ubuntu, Mint e derivados)

1. Baixe o arquivo e dê dois cliques nele.
2. Confirme a instalação pelo gerenciador de aplicativos do seu sistema.
3. Abra **Gaspar** pelo menu de aplicativos. O **Gaspar BlackBox** aparece no
   mesmo menu.

### Linux em qualquer distribuição, sem instalar

1. Baixe o arquivo, clique com o botão direito, abra **Propriedades**, vá em
   **Permissões** e marque **Permitir executar**.
2. Dê dois cliques no arquivo.

O Gaspar precisa de uma sessão gráfica **X11** (também funciona em **XWayland**).
Em Wayland puro, o mascote pode aparecer com um fundo quadrado e o clique pode
não atravessar.

> Prefere seguir com telas e a lista de arquivos dos dois lados? A
> [página de instalação](https://wiki.caracore.com.br/gaspar/instalacao.html)
> é o guia oficial.

## O que ele faz por você

- **Dá vida à tela:** o mascote flutua e se movimenta suavemente entre os cantos.
- **Mantém seu status ativo, quando você liga a simulação:** Teams e Slack param
  de mostrar você como ausente.
- **Respeita sua ausência:** só age depois de 60 segundos sem mouse ou teclado.
- **Registra o que aconteceu:** você abre os registros pelo botão **Abrir logs**.
- **Envia SMS pelo celular, quando você liga a ponte:** o PDV pede, o Gaspar
  entrega ao celular e o aparelho dispara a mensagem.
- **Bloqueia telemetria (opcional):** o BlackBox desliga e religa um conjunto
  de endereços de rastreamento, sem estragar nada do sistema.

## O que ele não faz

| Proteção | O que isso significa no dia a dia |
| --- | --- |
| Não rouba o foco | Você continua digitando na janela em que estava. |
| Não bloqueia cliques | Clicar na área do mascote atravessa para o que está atrás dele. |
| Não atrapalha quem está trabalhando | Ele espera você ficar ausente antes de agir. |
| Não mexe no seu mouse | Quando age, faz movimentos curtos e devolve o cursor ao lugar original. |
| Não cobre o painel | Enquanto a janela de configuração está aberta, o mascote fica atrás dela. |
| Não aparece em tela cheia | Em vídeos, jogos e apresentações, ele se esconde e as ações pausam. |
| Não torna a tela ilegível | Ele fica quase transparente quando o cursor se aproxima. |
| Não some sem aviso | Ao fechar o painel, ele continua perto do relógio; só sai quando você escolhe **Sair**. |
| Só pergunta sobre versão nova | O Gaspar consulta o canal oficial da Cara Core para saber se existe atualização. Nenhum dado seu, de venda ou de mensagem sai do computador. |
| Não mexe em outros sistemas | Ele não conversa com Mercado Pago, PlugNotas nem com o PDV; só recebe pedidos de SMS no próprio computador. |

## SMS pelo celular

O Gaspar também faz a ponte entre o PDV e um celular Android. Funciona assim:

1. O PDV pede a mensagem ao Gaspar, no mesmo computador.
2. O Gaspar entrega o pedido ao celular pela rede Wi-Fi da loja.
3. O celular dispara pelo chip e avisa quando o chip aceitou e quando a
   operadora confirmou a entrega.

Na janela **Celular / SMS** você pareia o aparelho lendo um QR code, faz um
envio de teste e acompanha os últimos resultados, com a marca de **enviado** (o
chip aceitou) e **entregue** (a operadora confirmou). O texto da mensagem viaja
fechado: só o computador da loja e o celular pareado conseguem abrir.

Para usar, são três coisas:

1. **Gaspar instalado** no computador.
2. **Aplicativo do celular instalado** — na primeira abertura, aceite a permissão
   de SMS e, no Android 13 ou mais novo, a de notificações.
3. **Celular e computador na mesma rede Wi-Fi**, com o Gaspar aberto.

Depois disso: abra **Celular / SMS**, marque **Ponte ativa**, clique em
**Parear celular** e leia o QR com o aplicativo do celular. A ponte começa
desligada: a porta do computador só abre depois que você marca **Ponte ativa**.
O pedido só é aceito quando vem do próprio computador, e há limite de mensagens
por número e por dia.

O uso no dia a dia e os limites estão em
[SMS no dia a dia](https://wiki.caracore.com.br/gaspar/sms.html), e o cuidado com
os dados em [Segurança e privacidade](https://wiki.caracore.com.br/gaspar/privacidade.html).

## Conhecendo o painel

O painel é rolável e se ajusta à altura da tela.

### Liga e desliga

| Controle | O que faz |
| --- | --- |
| **Ativar** / **Parar** | Começa ou interrompe as ações do mascote. Vem desligado, e **Ativar** só funciona depois que você escolhe ao menos uma ação (mouse, tecla ou Teams/Slack). |
| **Iniciar simulação ao abrir** | Começa automaticamente quando o app abre. Vem desligado. |
| **Movimentar o mouse** | Liga ou desliga o deslocamento suave do cursor. Vem desligado. |
| **Sinal sonoro** | Toca um som ao final de cada ciclo. Vem desligado. |
| **Gaspar flutuante** | Mostra ou esconde o mascote. |
| **Manter Teams/Slack ativo** | Além da tecla, manda um pequeno sinal de atividade. Vem desligado. |
| **Iniciar com o sistema** | Abre o Gaspar junto com o Windows ou com a sessão Linux, já minimizado. |

### Discrição

| Controle | O que faz |
| --- | --- |
| **Agir somente quando eu estiver ausente** | Recomendado. Espera 60 segundos sem mouse ou teclado. |
| **Pausar em tela cheia** | Esconde o mascote e pausa as ações em vídeos, jogos e apresentações. |
| **Intervalo** | Tempo entre uma ação e outra. Vai de 10 segundos a 1 hora. |
| **Tecla** | Nenhuma (padrão), F15 (recomendada), Shift ou Espaço. Escolha uma tecla ou o mouse para o **Ativar** ter o que fazer. |
| **Opacidade do Gaspar** | De 50% a 100%. O padrão dá o efeito translúcido. |

### Botões

| Botão | O que faz |
| --- | --- |
| **Ocultar** | Esconde o painel e deixa o app perto do relógio. |
| **Tirar o Gaspar da tela** | Remove o mascote da tela. O que estiver ligado continua funcionando. O botão vira **Trazer o Gaspar de volta**. |
| **Celular / SMS** | Abre a ponte de SMS: pareamento, teste e acompanhamento. |
| **BlackBox** | Abre a ferramenta opcional de bloqueio de telemetria. |
| **Abrir logs** | Abre os registros do Gaspar e a pasta onde eles ficam. |
| **Sair** | Encerra o Gaspar de verdade. |

A área de **Status** mostra se o mascote está agindo, quanto falta para a próxima
vez e quantas vezes ele já agiu.

## O ícone perto do relógio

O ícone oferece **Abrir painel**, **Simulação ativa**, **Gaspar flutuante** e
**Sair**. Fechar o painel pelo botão da janela **não encerra o app**: ele
continua ali, com o mascote na tela. Use **Sair** para encerrar de verdade.

## Seus arquivos e sua privacidade

- Configurações e registros ficam **somente no seu computador**.
- O Gaspar consulta apenas o canal oficial de atualização, para saber se existe
  versão nova. Nenhum dado seu, de venda ou de mensagem é enviado.
- As mensagens de SMS circulam entre o seu computador e o seu celular, pela rede
  da loja.
- A pasta de dados guarda a chave que pareia o celular: **não compartilhe essa
  pasta** com ninguém.

## O que vem na próxima versão

O que ainda **não** está nos instaladores publicados:

- **Chamada automática do PDV:** o PDV pedir a mensagem ao Gaspar sozinho, ao
  fechar a venda. Hoje o envio parte do painel do Gaspar ou de quem integra o
  PDV.

Para atualizar, baixe o instalador novo na página de
[Releases](https://github.com/chmulato/caracore-mascote/releases) e execute por
cima: suas preferências são mantidas.

## Perguntas frequentes

**Ele vai mexer no meu mouse enquanto eu trabalho?**
Não. Com **Agir somente quando eu estiver ausente** marcado, ele espera 60
segundos sem mouse ou teclado. Mesmo quando age, o movimento é curto e o cursor
volta para onde estava.

**Ele aparece durante uma reunião, vídeo ou jogo?**
Não. Com **Pausar em tela cheia** marcado, o mascote se esconde e as ações param
enquanto a tela cheia estiver ativa.

**Como faço para ele sumir da tela?**
Clique em **Tirar o Gaspar da tela**. O mascote some, mas o app continua
funcionando e o que estiver ligado segue ativo. Para voltar, clique em **Trazer o
Gaspar de volta**.

**O Gaspar usa a internet?**
Só para perguntar ao canal oficial se existe versão nova. Nada seu, de venda ou
de mensagem sai do computador, e as mensagens de SMS circulam pela rede da loja.

**Ele mexe nas conexões do Mercado Pago ou do PlugNotas?**
Não. O Gaspar não conversa com esses serviços, não intercepta nada da sua
internet e não altera as configurações de rede do computador.

**O que é o BlackBox? Preciso ser administrador para usar o Gaspar?**
O BlackBox é uma ferramenta opcional que bloqueia endereços de rastreamento da
Microsoft e do Application Insights. O bloqueio é reversível e fica só nesses
destinos: não inclui login da Microsoft, marketplace de extensões nem os sistemas
do PDV. Só ele pede permissão de administrador; o mascote e a ponte de SMS não.
Detalhes em [BlackBox](https://wiki.caracore.com.br/gaspar/blackbox.html).

**Por que o antivírus ou o Windows reclamam?**
O Gaspar não tem o selo pago de editor que o Windows espera ver, e o aviso aparece
por causa disso — não por causa do que o programa faz. Se você baixou o arquivo da
nossa página de download, pode liberar. Se recebeu o arquivo por outro caminho,
não execute.

**Como o Gaspar se atualiza?**
Ele avisa quando existe versão nova e mostra **Atualizar agora**, **Depois**,
**Pular esta versão** e **Ver novidades**. Nada é instalado sem a sua permissão.
O passo a passo está em [Atualização do Gaspar](https://gaspar.caracore.com.br/atualizacao.html).

**Como desinstalar?**
No Windows, use **Aplicativos instalados** e remova **Gaspar - Mascote Cara
Core**. No Linux, desinstale pelo gerenciador de aplicativos. Se você usa a
versão que não instala nada, basta apagar o arquivo baixado.

## Deu problema

| O que aparece | O que fazer |
| --- | --- |
| O mascote tem um quadrado de fundo no Linux | Sua sessão não é X11. Entre numa sessão X11 ou XWayland. |
| O mouse se mexe enquanto você trabalha | Confirme **Agir somente quando eu estiver ausente**. Se ainda incomodar, desmarque **Movimentar o mouse**. |
| O mascote cobre o painel | Feche e reabra o painel: ele volta para trás. |
| O BlackBox não abre | Use o instalador completo, que traz o Gaspar e o BlackBox. Ele também aparece no menu iniciar. |
| O celular não aparece na janela **Celular / SMS** | Confira a rede Wi-Fi, se o aplicativo está aberto e a bateria do aparelho. O guia de instalação tem o passo a passo. |

## Precisa de ajuda

- **Site oficial:** [gaspar.caracore.com.br](https://gaspar.caracore.com.br/)
- **Instalação no computador e no celular:** [página de instalação](https://wiki.caracore.com.br/gaspar/instalacao.html)
- **SMS no dia a dia:** [guia de SMS](https://wiki.caracore.com.br/gaspar/sms.html)
- **Segurança e privacidade do SMS:** [guia de privacidade](https://wiki.caracore.com.br/gaspar/privacidade.html)
- **Atualização:** [página oficial](https://gaspar.caracore.com.br/atualizacao.html)
- **BlackBox e telemetria:** [guia do BlackBox](https://wiki.caracore.com.br/gaspar/blackbox.html)

## Licença e créditos

Distribuído sob a licença **MIT**. Consulte [LICENSE](LICENSE).

- **Cara Core Informática**
- Autor: Christian Vladimir Uhdre Mulato
- Campo Largo, Paraná - Brasil
- 2026

A marca, o nome Gaspar e os ativos visuais pertencem à Cara Core Informática. O
código pode ser reutilizado conforme a licença MIT.
