# App do celular - Enviar SMS

Este é o aplicativo que roda no celular Android da loja. Ele é a outra metade da
ponte de SMS: o computador pede, o celular dispara pelo chip e avisa o resultado.
O guia de uso no dia a dia está em
[SMS no dia a dia](https://wiki.caracore.com.br/gaspar/sms.html).

> **Publicado hoje:** a versão **1.7**, de 15/11/2026, na
> [Release Android 1.7](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.7).
> Ela traz o visual do Gaspar no aparelho, o painel da rede Wi-Fi da loja e a
> confirmação de operações do PDV na tela do celular. Nessa versão a licença é
> **digitada** — o aplicativo não lê suas mensagens —, ele **não** pede
> liberação da economia de bateria, o aviso de fim de backup do PDV só é aceito
> quando traz a chave do próprio aparelho e a tela de confirmação só abre depois
> que você toca no aviso.

> **Qual versão combina com qual:** o aplicativo **1.7** acompanha o Gaspar
> **1.7.1** ou mais novo no computador. Quem ainda usa o Gaspar **1.7.0** fica
> com o aplicativo **1.2**. As versões **1.6** e **1.5** continuam publicadas, e
> a **1.4** é a única sem a trava que impede outros aplicativos de ler o estado
> da licença.

## Para que serve

- Recebe o pedido de mensagem do computador da loja, pela rede Wi-Fi, e só ele
  consegue abrir o pedido: a chave fica guardada no próprio aparelho.
- Dispara o SMS pelo chip sem abrir a tela de mensagens.
- Devolve ao computador o "o chip aceitou" e o "a operadora entregou".
- Deixa o computador encontrar o celular sozinho na rede da loja.
- Pareia lendo o QR code que aparece no Gaspar.
- Guarda a senha do Wi-Fi da loja e gera um QR para outro aparelho entrar na
  rede, depois de você confirmar com digital, rosto ou PIN.
- Mostra na tela do celular os pedidos de aprovação de desconto, cancelamento e
  sangria, com prazo e histórico.

## Preparar o celular

1. Instale o aplicativo no aparelho (Android 7.0 ou mais novo).
2. Abra o aplicativo e toque em **Permitir** quando ele pedir para enviar SMS e,
   no Android 13 ou mais novo, para mostrar notificações.
3. Deixe celular e computador na mesma rede Wi-Fi, com o Gaspar aberto.
4. No Gaspar, abra **Celular / SMS**, clique em **Parear celular** e leia o QR
   com o aplicativo.
5. Se a licença não vier no QR, digite a chave na tela de configuração do app.

A versão 1.7 **não** pede liberação da economia de bateria. Deixar o aplicativo
como "Sem restrições" nos ajustes do Android continua recomendado para o serviço
não ser fechado em segundo plano, mas a escolha é sua.

## O que ele não faz

| Compromisso | O que isso significa no dia a dia |
| --- | --- |
| Não lê mensagens | Desde a 1.7 ele não tem acesso às suas conversas: a licença é digitada ou vem do QR. |
| Não deixa outros aplicativos enviarem | Nada instalado no celular consegue usar o seu chip pelas costas. |
| Não manda SMS direto do computador | O antigo disparo por cabo USB foi desligado de propósito, para o celular não virar máquina de mensagem. |
| Tem teto de envio | São até 300 mensagens por dia no aparelho, e um pedido repetido é recusado. |
| Não guarda número nem texto | O histórico do app registra o que aconteceu, sem o conteúdo das mensagens. |
| Não envia nada para a internet | O caminho é a rede da loja, entre o seu computador e o seu celular. |

## Limitações conhecidas

- O "entregue" depende da operadora devolver o recibo. Quando ela não devolve, o
  pedido fica marcado como **enviado**, o que já confirma que a mensagem saiu do
  celular.
- A licença digitada confere o formato e o mês, sem carimbo digital.
- O pedido de confirmação chega como notificação comum: o celular precisa estar
  desbloqueado e você precisa tocar no aviso para abrir a tela.
- O aviso de fim de backup do PDV só é aceito quando vem endereçado ao app e com
  a chave do aparelho. Um PDV que ainda não manda essa chave tem o aviso recusado
  até ser atualizado.
- O pareamento conversa com o computador pela rede local sem cifra de site: é a
  rede da loja, e o pedido em si viaja fechado.
- O SMS enviado fica na caixa **Enviadas** do aplicativo de mensagens do celular,
  como qualquer SMS. O Gaspar não controla essa cópia.
- As versões 1.6 e 1.7 foram exercitadas em aparelho de teste (emulador), ainda
  não em celular físico, e o lado do computador na confirmação de operações ainda
  não existe.

## Seus dados

O que o aplicativo guarda, onde guarda e por quanto tempo está em
[Segurança e privacidade](https://wiki.caracore.com.br/gaspar/privacidade.html).
Quem tem o QR de pareamento pode ligar um aparelho à sua ponte: não fotografe nem
compartilhe esse código.

## Para quem compila

O aplicativo é um projeto Android normal. O ambiente, os atalhos de build, a
assinatura de release, a instalação por cabo e os erros conhecidos estão em
[BUILD.md](BUILD.md). O que a versão faz está em
[README-PDV-SMS.md](README-PDV-SMS.md), e o estado de cada versão em
[STATUS_ATUAL.md](STATUS_ATUAL.md).
