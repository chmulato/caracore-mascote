# Ponte local de SMS (Gaspar + celular Android)

Este guia explica como o Gaspar entrega ao celular os SMS pedidos pelo PDV.
Ele foi escrito para quem usa o sistema no dia a dia; os detalhes de
programação ficam no fim.

> **Estado atual:** o recurso está no código-fonte. Os instaladores 1.6.0 já
> publicados ainda não incluem esta ponte e precisam ser recompilados para
> recebê-la.

## Em uma frase

O PDV pede o SMS, o Gaspar entrega o pedido ao celular pela rede Wi-Fi e o
celular dispara a mensagem pelo chip. O Gaspar guarda o resultado de cada envio
e mostra na tela.

O mascote pode ser **tirado da tela** pelo botão **Tirar o Gaspar da tela** sem
parar a ponte: o app continua na bandeja e segue atendendo o PDV.

## Como funciona

```text
PDV  --pedido-->  Gaspar (no computador)  --Wi-Fi-->  Celular  --SMS-->  Cliente
                        ^                                  |
                        +-------- celular se anuncia -----+
```

1. O celular e o computador ficam na **mesma rede Wi-Fi**.
2. O Gaspar mostra um **QR de pareamento**; o aplicativo do celular lê o código.
3. O PDV chama o endereço local do Gaspar e informa número, mensagem e o código
   da venda.
4. O Gaspar cifra o pedido e envia ao celular.
5. O celular confirma que recebeu o pedido e dispara o SMS.
6. O Gaspar registra o resultado e mostra em **Celular / SMS**.

O Gaspar fica **no caminho**: se ele estiver fechado ou a ponte estiver
desligada, o PDV não consegue pedir o SMS. O PDV deve tratar a falha como "não
enviado" e tentar de novo mais tarde.

## Preparar o celular

1. Instale o aplicativo Android deste repositório (pasta `android/`). As
   instruções de compilação e instalação estão em
   [android/README.md](../android/README.md).
2. Abra o aplicativo e conceda as permissões de SMS.
3. Desative a otimização de bateria para o aplicativo, para o serviço não ser
   encerrado pelo Android.
4. Mantenha o celular e o computador na mesma rede Wi-Fi. Redes de convidados
   que isolam os aparelhos podem impedir a conversa.

## Parear pelo Gaspar

1. Abra o Gaspar e clique em **Celular / SMS**.
2. Confirme que **Ponte ativa** está marcado.
3. Clique em **Parear celular**. Um QR aparece em uma janela separada.
4. No celular, abra o aplicativo e use a leitura de QR.
5. Quando o celular termina o diagnóstico, o Gaspar fecha o QR e mostra
   **Celular pareado**.

O QR vale por **15 minutos** e só pode ser usado **uma vez**. Se expirar, clique
em **Parear celular** de novo para gerar outro.

Se o Gaspar não encontrar o celular, clique em **Procurar celular**. O celular
responde automaticamente quando o aplicativo está aberto e o serviço está
ligado.

## Enviar um teste

Na janela **Celular / SMS**:

1. Digite o número com DDD (por exemplo, `11999999999` ou `+5511999999999`).
2. Deixe ou ajuste a mensagem de teste.
3. Clique em **Enviar teste**.
4. A lista **Últimos envios** mostra o estado: fila, enviando, enviado ou
   falhou.

O teste não precisa do PDV. Ele serve para confirmar o pareamento e a rede.

## Integrar com o PDV

Na janela **Celular / SMS**, a área **Integração com o PDV** mostra o
**endereço** e o **token** que o PDV precisa usar. O PDV envia o número, a
mensagem e o código da venda; o Gaspar confere o token, coloca o pedido na fila
e responde com um identificador para acompanhar o resultado.

Se você só opera a loja, não precisa mexer nisso: quem instala o PDV configura
essa parte uma vez. O endereço exato, os campos aceitos e os códigos de resposta
estão no [guia técnico](tecnico.md#api-para-o-pdv).

## Limites de segurança e custo

- **20 pedidos por minuto** e **300 por dia**, por padrão. Podem ser ajustados
  no arquivo `sms_config.json`.
- Fila de até **100 pedidos**.
- **2 tentativas** quando o celular está fora do ar; depois o pedido é marcado
  como falha.
- Mensagem de até **480 caracteres**.
- O mesmo `venda_id` não gera segundo SMS dentro de 24 horas.

## Segurança

- O pedido vai cifrado (AES-256-GCM, um cadeado digital forte); a chave é
  criada pelo Gaspar e entregue ao celular pelo QR.
- O PDV precisa do **token da API**. Se o token vazar, clique em **Gerar novo**
  na janela do celular e atualize o cadastro do PDV.
- O token de pareamento é de uso único e expira em 15 minutos.
- A conversa entre Gaspar, celular e PDV acontece **só na rede interna**, sem
  cadeado HTTPS. Use uma rede confiável e não exponha o Gaspar para a internet.
- Os segredos ficam em `sms_config.json`, na pasta de dados do usuário, com
  permissão restrita. Não versionar esse arquivo.

## Onde ficam os arquivos

Na pasta de dados do Gaspar (`%APPDATA%\CaraCore\Gaspar\` no Windows ou
`~/.config/caracore/gaspar/` no Linux):

| Arquivo | Conteúdo |
| --- | --- |
| `sms_config.json` | Chave de pareamento, token da API, limites e preferências. |
| `sms_state.json` | Últimos 500 pedidos e o estado de cada um. |
| `sms_log.jsonl` | Trilha de envios com o número mascarado; rotaciona em 1 MB. |
| `cycle_log.txt` | Eventos gerais do Gaspar. |

## Problemas comuns

**O celular não é encontrado**

- Confira se está na mesma rede Wi-Fi e se a rede não isola os aparelhos.
- Abra o aplicativo no celular e confirme que o serviço está ligado.
- Desative a otimização de bateria para o aplicativo.
- Verifique se o firewall do Windows permite o Python/Gaspar na rede privada.

**O QR expirou**

Gere outro em **Parear celular**. O código anterior deixa de valer.

**A porta 8766 está ocupada**

Feche outra instância do Gaspar ou altere `http_port` em `sms_config.json`.
Depois reabra o Gaspar e gere um novo QR, porque o endereço muda.

**O PDV recebe erro de token**

O token foi trocado. Copie o token atual na janela **Celular / SMS** e atualize
o cadastro do PDV.

**O envio falha sempre**

- Confira crédito e chip do celular.
- Veja se o aplicativo tem permissão de SMS e está com o serviço ativo.
- No Android, verifique se o sistema não encerrou o aplicativo por economia de
  bateria.
- Lembre que o estado **enviado** significa "entregue ao celular", não
  "entregue ao cliente". O recibo da operadora ainda não é devolvido.

## O que ainda falta

- **Recibo de entrega da operadora:** hoje o Gaspar confirma que o celular
  recebeu o pedido, não que o cliente recebeu o SMS.
- **Assinatura da licença:** o aplicativo valida formato e mês da chave, sem
  assinatura digital.
- **Conexão com cadeado:** a conversa na rede interna não usa HTTPS.
- **Android atualizado:** versões novas do Android podem encerrar o aplicativo
  em segundo plano e exigir que ele seja reaberto.
- **Fila sem o Gaspar:** o PDV depende do Gaspar ligado para enviar.

## Para quem programa

O código da ponte está em `gaspar/sms/`, o aplicativo do celular está em
`android/` e os testes em `tests/test_sms.py`. O protocolo, a API para o PDV, a
criptografia e o passo a passo de build estão no
[guia técnico](tecnico.md#ponte-local-de-sms).
