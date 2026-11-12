# Termo de segurança e privacidade do SMS

Este documento explica, em linguagem de loja, o que o Gaspar faz com os dados do
SMS que o PDV pede: o que protege, o que guarda, por quanto tempo e o que
continua fora do alcance dele. Ele vale para a ponte local de SMS descrita em
[sms.md](sms.md) e serve de anexo para quem precisa demonstrar cuidado com a
**LGPD**.

> **Versão do documento:** 11/11/2026. Ele descreve a versão em
> desenvolvimento; a versão publicada (Gaspar **1.7.0** e aplicativo **1.2**)
> ainda não tem a criptografia de ponta a ponta nem a auditoria sem conteúdo.
> Enquanto o aplicativo do celular não for atualizado, o Gaspar recusa o
> pareamento: não existe envio "meio protegido".

## Em uma frase

O número e o texto passam pelo Gaspar **fechados com a chave do celular**, não
são gravados em lugar nenhum e o registro de auditoria guarda **apenas o
"envelope" do envio** — data, venda, modelo, estado e códigos que não se
revertem em número nem em texto.

## Quem participa

| Papel | Quem é | O que faz |
| --- | --- | --- |
| Controlador dos dados | o **lojista** | decide enviar o SMS e responde pela base legal |
| Operador / ferramenta | a **CaraCore**, pelo Gaspar | entrega o pedido e guarda metadados mínimos |
| Aparelho de envio | o **celular pareado** | abre o pacote, dispara pelo chip e devolve o comprovante |
| Terceiros | a **operadora** e o **aparelho do cliente** | transportam e recebem o SMS, como qualquer mensagem |

O Gaspar é um programa que roda **no computador da loja**. Não há servidor da
CaraCore no caminho e nada é enviado para a internet.

## O caminho do pedido

```text
PDV (mesmo computador)  --rede interna-->  Gaspar (ponte)  --Wi-Fi-->  Celular  --operadora-->  Cliente
                                                    |                    |
                                                    +-- comprovante -----+
```

1. O PDV entrega ao Gaspar o número, o modelo da mensagem e o código da venda.
   Essa conversa acontece **dentro do próprio computador** e só é aceita da
   própria máquina.
2. O Gaspar confere token, assinatura e limites, monta o texto do modelo e
   **fecha o pacote** com a chave pública do celular. O texto e o número saem da
   memória do Gaspar nesse momento.
3. O pacote segue pela Wi-Fi, por cima de outra camada cifrada com o segredo do
   pareamento.
4. O celular abre o pacote, dispara o SMS e devolve "aceito" e, quando a
   operadora confirma, "entregue".
5. O Gaspar anota **só metadados** e mostra na janela **Celular / SMS**.

## O que é guardado (e o que não é)

| Dado | Passa pelo Gaspar? | Fica guardado? | Onde e por quanto tempo |
| --- | --- | --- | --- |
| Número do cliente | sim, só na memória | **não** em texto; só dentro do pacote cifrado | `sms_state.json` (envelope), até 500 pedidos |
| Texto da mensagem | sim, só na memória | **não** em texto; só dentro do pacote cifrado | `sms_state.json` (envelope) |
| Código da venda | sim | sim | estado e auditoria, 90 dias |
| Modelo usado | sim | sim (nome do modelo) | estado e auditoria, 90 dias |
| Estado e horários | sim | sim | estado e auditoria, 90 dias |
| Motivo da falha | sim | sim, em código curto | estado e auditoria, 90 dias |
| Marca do destino e do conteúdo | gerada localmente | sim, código de 16 bytes | estado e auditoria, 90 dias |
| Endereço IP da rede | sim | **não** | — |
| Nome, CPF, e-mail do cliente | **não** | **não** | — |

O PDV só envia número, modelo, variáveis do modelo e código da venda. O Gaspar
não pede, não recebe e não guarda nome, CPF, endereço ou qualquer outro dado do
cliente. Não há dado sensível (saúde, religião, biometria) em nenhum ponto.

A **marca** (`#a1b2c3d4`) é um resumo calculado com uma chave secreta do
computador. Ela é sempre igual para o mesmo número, então serve para perceber
"dois SMS para o mesmo destino", mas não revela o número. A marca do conteúdo
funciona do mesmo jeito para o texto.

## Criptografia de ponta a ponta

- O **celular** cria um par de chaves quando o aplicativo é pareado. A chave
  privada fica protegida pelo cofre do próprio Android (Keystore) e **nunca sai
  do aparelho**; a chave pública é enviada ao Gaspar no pareamento.
- Para cada pedido, o Gaspar cria uma chave temporária, combina com a chave
  pública do celular e produz uma chave de mensagem só daquele pedido. O
  identificador do pedido entra como "endereço" do lacre, então um pacote não
  pode ser reaproveitado em outro pedido.
- O resultado é **AES-256-GCM**, o mesmo tipo de cadeado usado por bancos e
  navegadores, com 128 bits de autenticação: se alguém alterar um byte no
  caminho, o celular recusa o pacote em vez de enviar lixo.
- Por cima, o canal Wi-Fi continua cifrado com o segredo de 32 bytes criado no
  pareamento. São **duas camadas**: uma para o caminho, outra para o conteúdo.

Quem consegue ler o quê:

| Quem | Lê o número e o texto? |
| --- | --- |
| O celular pareado | sim, é o destinatário do envelope |
| O Gaspar, depois de fechar o pacote | **não** |
| Quem abrir o `sms_state.json` | **não** (só cifra) |
| Alguém espiando a Wi-Fi | **não** (duas camadas de cifra) |
| A operadora e o aparelho do cliente | sim — o SMS chega em claro, como qualquer SMS |

## Auditoria sem conteúdo

Toda mudança de estado grava uma linha em `sms_audit.jsonl`, no formato JSONL
(uma linha por evento). Um exemplo:

```json
{"ts":"2026-11-11T14:22:05Z","evento":"fila","id":"7f3c...","venda":"venda-123","modelo":"venda_confirmada","destino":"3f2a9c...","conteudo":"9c1b44...","status":"fila","tentativa":0,"selado":true,"origem":"pdv"}
{"ts":"2026-11-11T14:22:07Z","evento":"entregue","id":"7f3c...","venda":"venda-123","modelo":"venda_confirmada","destino":"3f2a9c...","conteudo":"9c1b44...","status":"entregue","tentativa":1,"selado":true,"origem":"pdv"}
```

Regras que o próprio código impõe:

- **Campos proibidos**: número, mensagem, envelope, blob, IP, detalhe. Uma
  tentativa de gravar qualquer um deles gera erro e a linha não é escrita.
- **Campos permitidos**: identificador, venda, modelo, marcas, estado, motivo,
  tentativa, selado e origem. Qualquer outro nome é recusado.
- **Tamanho**: textos são cortados em 64 caracteres; a trilha rotaciona em 2 MB
  (um arquivo anterior é mantido como `.1`).
- **Retenção**: 90 dias por padrão (ajustável em `sms_config.json` entre 1 e
  3650 dias). A limpeza roda quando o Gaspar abre.
- **Direito ao esquecimento**: o botão **Apagar histórico** apaga os pedidos e a
  trilha inteira, inclusive o arquivo rotacionado.
- **A lista da tela** mostra só a marca do destino, o modelo e o estado — nunca
  o número ou o texto.

A auditoria serve para responder "houve envio para esta venda?", "quantas
tentativas?", "por que falhou?" e "de onde partiu o pedido?", sem reconstruir o
conteúdo. Ela não serve para reenviar nem para reproduzir a mensagem: o texto
não existe mais em claro depois do lacre.

## Bases legais e direitos (LGPD)

O Gaspar foi desenhado para atender aos princípios do art. 6º: **finalidade**
(entregar o SMS pedido pela loja), **adequação**, **necessidade** (só número,
modelo e código da venda), **transparência** (esta página e a janela mostram o
que é guardado), **segurança** e **prevenção**.

- **Base legal**: é escolha do lojista. Para confirmação de venda, as bases
  usuais são **execução de contrato** (art. 7º, V) ou **legítimo interesse**
  (art. 7º, IX) com avaliação simples de que o cliente espera esse aviso. Não há
  consentimento colhido pelo Gaspar e não há dado sensível.
- **Titular**: pode pedir confirmação de tratamento, acesso aos metadados,
  correção, eliminação e informação sobre compartilhamento. O caminho prático é
  o lojista consultar a janela **Celular / SMS** e usar **Apagar histórico**
  quando for o caso; não existe conteúdo a entregar porque ele não é guardado.
- **Compartilhamento**: não há. O dado não sai do computador da loja nem do
  celular pareado, exceto o próprio SMS entregue à operadora.
- **Transferência internacional**: não há.
- **Segurança**: cifra de ponta a ponta, token de API, assinatura por pedido,
  limites por destinatário, trilha de auditoria, permissões restritas nos
  arquivos de segredo.
- **Incidente**: se o token da API vazar, gere outro em **Gerar novo** e atualize
  o PDV. Se o celular se perder, pareie outro aparelho (a chave antiga deixa de
  valer). Em caso de vazamento de dados pessoais, a comunicação à ANPD e ao
  titular é responsabilidade do controlador (lojista); a CaraCore apoia com o
  registro de auditoria e o relato do que ficou exposto.

## Proteção contra uso como máquina de spam

O mesmo recurso não pode virar ferramenta de envio em massa. As travas são:

| Trava | O que impede |
| --- | --- |
| Só `127.0.0.1` na API | pedido de outra máquina da rede é recusado |
| Token + assinatura HMAC com hora e número único | pedido forjado, repetido ou atrasado é recusado |
| Só modelos prontos | o PDV não escolhe texto livre |
| 1 por hora e 3 por dia por número | bombardeio de um mesmo cliente |
| Mesmo texto para o mesmo número em 30 min | duplicidade acidental ou proposital |
| 300 SMS por dia no próprio celular | teto mesmo se o computador for comprometido |
| Fila de 100 e 20 por minuto | picos e loops de integração |
| `venda_id` único por 24 h | reenvio em cascata da mesma venda |

## Papéis e responsabilidades

- **CaraCore** entrega o software, mantém a cifra, a auditoria e as travas acima
  e documenta o que o programa faz. Não tem acesso aos dados da loja.
- **Quem instala** pareia o celular, guarda o token do PDV em lugar seguro e
  mantém o computador e o celular atualizados.
- **Lojista (controlador)** define a base legal, orienta a equipe, atende os
  pedidos dos titulares e decide quando apagar o histórico.
- **Equipe da loja** usa a janela **Celular / SMS** e não compartilha o token
  nem o QR de pareamento.

## Limites conhecidos (o que este desenho não resolve)

Ser honesto aqui é parte do termo:

- **Computador comprometido**: quem controla o computador da loja pode ler o
  pedido no instante em que ele chega, antes do lacre, ou pedir SMS com o token.
  A cifra protege o caminho e o arquivo em repouso, não uma máquina invadida.
- **Rede interna sem HTTPS**: a conversa com o Gaspar não usa certificado; por
  isso a API só aceita chamadas da própria máquina e não deve ser exposta à
  internet.
- **Marca reversível por tentativa**: se a chave de auditoria vazar **e** alguém
  tiver uma lista de números, pode confirmar quais números aparecem na trilha.
  A marca não entrega o número diretamente, mas confirma um palpite. A chave
  fica em `sms_config.json` com permissão restrita.
- **Celular nas mãos de terceiro**: o aplicativo pode enviar enquanto estiver
  pareado e ativo. Perdeu o aparelho, pareie outro; o teto diário do celular
  limita o estrago até lá.
- **Caixa "Enviadas" do celular**: o SMS enviado fica no histórico do aplicativo
  de mensagens do próprio Android, como qualquer SMS digitado à mão. O Gaspar
  não controla essa cópia; ela pode ser apagada pelo usuário do aparelho.
- **Backup do Android**: o sistema pode copiar as preferências do aplicativo
  para a conta Google. A chave privada do envelope está presa ao cofre do
  aparelho e não funciona em outro celular, mas o segredo de pareamento pode ir
  no backup. O pareamento novo resolve.
- **Logs do Android**: o aplicativo registra estado e erros técnicos no log do
  sistema, sem número nem texto. Um aparelho com depuração ligada expõe esses
  logs a quem estiver conectado por cabo.
- **Modo antigo (não recomendado)**: desligar `e2e_required` em
  `sms_config.json` faz o número e o texto voltarem a ser gravados em claro no
  `sms_state.json` e a viajar apenas dentro do canal AES. O padrão é ligado, e a
  próxima versão deve remover essa opção.
- **Entrega e leitura**: "entregue" é o recibo da operadora; não há confirmação
  de que o cliente leu.
- **Versão publicada**: até a próxima versão dos dois lados, o recurso em
  produção é o da 1.7.0/1.2, sem envelope e sem auditoria sem conteúdo.

## Para quem programa

O termo resume o comportamento de `gaspar/sms/` (envelope em `e2e.py`, auditoria
em `audit.py`, estado em `store.py`, fila em `bridge.py`) e do aplicativo em
`android/src/main/java/br/com/caracore/pdv/sms/` (`E2ECrypto`, `E2EKeySender`,
`GatewayListenerService`). O detalhe do protocolo, dos campos e das rotas está
no [guia técnico](tecnico.md#ponte-local-de-sms); os testes que sustentam cada
afirmação deste termo estão em `tests/test_sms.py`.
