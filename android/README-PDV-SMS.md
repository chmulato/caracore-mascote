# PDV Enviar SMS - App do celular da loja

O aplicativo transforma um celular Android comum no celular de envio da loja. O
computador pede a mensagem, o celular dispara pelo chip e conta de volta o que
aconteceu. Nada disso passa por servidor da internet: a conversa é entre o
computador da loja e o celular dela, pela rede do estabelecimento.

O celular é quem manda a mensagem, então o que chega ao cliente tem o número da
loja, e o envio respeita o plano de SMS do chip.

## O que está publicado hoje

A versão **1.7** (de 15/11/2026), na
[Release Android 1.7](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.7).

O que a 1.7 mudou, em poucas palavras:

- **A licença é digitada.** O aplicativo parou de ler mensagens: antes ele
  consultava o SMS da licença, agora a chave é escrita na tela ou vem do QR de
  pareamento.
- **Não pede mais liberação da bateria.** Quem quiser deixar o app sem
  restrição ajusta isso nos ajustes do Android.
- **O aviso de fim de backup só vale com a chave do aparelho.** Um pedido de
  aviso sem a chave certa é recusado e registrado.
- **A confirmação aparece quando você toca.** O pedido de aprovação chega como
  notificação e a tela só abre depois do toque — nada aparece por cima da tela de
  bloqueio.
- **Continúa** com o visual do Gaspar, o painel da rede Wi-Fi da loja e o limite
  de 300 mensagens por dia no aparelho.

As versões **1.6** e **1.5** continuam publicadas nas releases próprias. A **1.4**
é a única sem a trava que impede outros aplicativos de lerem o estado da licença —
isso foi conferido no arquivo que está publicado, não só no código.

## Licença do Premium

A chave tem o formato que a Cara Core entrega e vale pelo mês indicado. Duas
maneiras de aplicar:

1. **Digitando no painel** do aplicativo, no cartão **Licença**. Um texto fora do
   formato é recusado na hora, com aviso, e nada é gravado.
2. **Pelo QR de pareamento**, que pode trazer a chave junto com o endereço do
   computador.

Quem sobe do 1.6 para a 1.7 precisa digitar a chave uma vez: a que já estava
salva continua valendo. O painel mostra **Licença Premium Ativa** em verde ou
**Licença Gratuita / Inativa** em vermelho.

## Permissões que o app pede

- **Enviar SMS** — é o serviço dele.
- **Notificações**, no Android 13 ou mais novo, para o pedido de aprovação
  aparecer.
- **Câmera**, só para ler o QR de pareamento.

Ele **não** pede acesso para ler ou receber mensagens, e não pede liberação da
economia de bateria.

## Rede Wi-Fi da loja

O painel **Wi-Fi da loja** guarda o nome e a senha da rede no próprio aparelho.
Depois de você confirmar com digital, rosto ou PIN, dá para ver a senha, copiar
ou gerar um QR para outro celular entrar na rede. A senha aparece por pouco tempo
na tela e some da área de transferência sozinha; em celular sem trava de tela o
aplicativo recusa revelar. Nada disso é enviado para servidor nenhum, e o app não
mexe no roteador.

## Aprovação de operações no celular

Com **Receber pedidos de confirmação** ligado, o computador pode pedir ao celular
a aprovação de **desconto**, **cancelamento** ou **sangria**. Cada pedido traz um
prazo curto e um valor máximo; pedido repetido ou fora das regras é recusado.
**Aprovar** exige digital, rosto ou PIN do próprio celular; **negar** pede uma
confirmação simples. A decisão fica no histórico do aparelho — as últimas 100 —
e é devolvida ao computador fechada; se o computador estiver desligado, a decisão
espera e é reenviada quando ele voltar.

O botão **Pedido de teste** cria um pedido marcado como teste no próprio aparelho,
para exercitar a tela sem o computador. Nada é enviado.

O lado do computador — mandar o pedido e receber a decisão — ainda não existe no
Gaspar: é a etapa que vem depois da validação em bancada.

## Aviso de fim de backup

O PDV avisa o celular quando o backup termina. Desde a 1.7 esse aviso só é aceito
quando vem endereçado ao aplicativo e traz a chave de 32 caracteres mostrada no
painel do app, no cartão **Backup do banco de dados**, com botão **Copiar token do
backup**. Sem a chave, nada é gravado. Um PDV que ainda não manda a chave
continua funcionando com o app **1.6** publicado; com a **1.7**, o aviso dele é
recusado até o PDV ser atualizado.

## Segurança em poucas palavras

- O celular cria um par de chaves no primeiro uso. A parte privada nunca sai do
  aparelho e a pública é entregue ao Gaspar no pareamento. Cada pedido só pode
  ser aberto pelo celular pareado e vale para aquele pedido.
- O tráfego na rede da loja vai cifrado, e o computador só aceita pedidos que
  venham da própria máquina, com limite de volume.
- Nenhum aplicativo instalado no celular consegue disparar mensagem pelo app: o
  caminho antigo por cabo USB foi desligado de propósito.
- O histórico do app registra estado e erros técnicos, sem número e sem texto. O
  SMS enviado fica na caixa **Enviadas** do aplicativo de mensagens, como
  qualquer SMS.
- A senha do Wi-Fi e as decisões de confirmação ficam guardadas no aparelho com a
  chave de segurança do próprio Android.
- Quem tem o QR de pareamento pode ligar um aparelho à sua ponte. Não fotografe
  nem compartilhe esse código; se desconfiar, pareie de novo pelo Gaspar.

O termo completo, com o que é guardado e por quanto tempo, está em
[Segurança e privacidade](https://wiki.caracore.com.br/gaspar/privacidade.html).

## Limitações conhecidas

- O "entregue" depende da operadora devolver o recibo; sem ele, o pedido fica em
  **enviado**, que já confirma a saída do celular.
- A licença digitada confere formato e mês, sem carimbo digital.
- O pareamento usa a rede local sem cifra de site no diagnóstico inicial; o
  pedido de mensagem em si vai fechado.
- O aplicativo ainda foi exercitado em aparelho de teste (emulador), não em
  celular físico, e o lado do computador na confirmação de operações ainda não
  existe.

---

## Para quem compila

Ambiente, atalhos de build, assinatura de release, instalação por cabo, a
estrutura do projeto e os erros conhecidos estão em
[BUILD.md](BUILD.md). O estado de cada versão está em
[STATUS_ATUAL.md](STATUS_ATUAL.md).
