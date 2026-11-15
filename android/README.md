# App Android - Enviar SMS

Este diretório guarda o aplicativo que roda no celular Android e dispara os SMS
pedidos pelo Gaspar. Ele é a outra metade da ponte local de SMS descrita em
[wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html).

> **O que está publicado hoje é a 1.7 (código 8)**, de 15/11/2026, na
> [Release Android 1.7](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.7).
> Ela mantém o envelope cifrado, a trava do provedor de licença, o ícone e o skin
> do Gaspar, o painel da senha do Wi‑Fi da loja e a confirmação de operações do
> PDV no celular. Ao mesmo tempo, reduz o que faz os verificadores de segurança
> desconfiarem do app: a licença é digitada na tela (o app não lê SMS), não pede
> isenção da economia de bateria, exige um token do PDV para aceitar aviso de
> backup, mostra a confirmação de operações só depois que o dono toca na
> notificação e compila para o Android 15 (alvo 35). A **1.6** e a **1.5**
> continuam disponíveis; o **1.4** não tem a trava do provedor. O Gaspar **1.7.1**
> ou mais novo usa a 1.7; o aplicativo **1.2** só atende o Gaspar **1.7.0**.

## Para que serve

- Recebe um pedido **cifrado de ponta a ponta** vindo do computador na mesma
  rede Wi-Fi e abre com a chave que só ele tem.
- Envia o SMS diretamente pelo chip do celular, sem abrir a tela de mensagens.
- Devolve ao Gaspar o "aceito" do chip e o "entregue" da operadora.
- Responde na rede local para o Gaspar encontrar o aparelho automaticamente.
- Lê o QR de pareamento gerado pelo Gaspar para guardar a chave e o endereço.
- Guarda a senha do Wi‑Fi da loja, mostra/copia/gera QR depois da confirmação do
  dono e testa se o computador responde.
- Pede aprovação de desconto, cancelamento e sangria no celular, com digital,
  rosto ou PIN, prazo e histórico.

O envio por cabo USB (ADB) foi **retirado**: a activity de envio não é mais
exportada e exige permissão interna de assinatura. O teste manual é feito pela
janela **Celular / SMS** do Gaspar.

## Como preparar o celular

1. Compile e instale o APK no aparelho (Android 7.0 ou superior).
2. Abra o aplicativo e conceda a permissão de **Enviar SMS** e, no Android 13
   ou superior, a de **notificações** (é por ela que o pedido de confirmação
   aparece).
3. Mantenha o celular e o computador na mesma rede Wi-Fi.
4. No Gaspar, abra a janela **Celular / SMS**, clique em **Parear celular** e leia o
   código com o aplicativo.
5. Se a licença não vier no QR, digite a chave na tela de configuração do app.

A 1.7 **não pede** isenção da economia de bateria. Deixar o app como "Sem
restrições" nas configurações do aparelho continua recomendado para o serviço
não ser encerrado em segundo plano, mas a escolha é do dono, nas configurações
do Android.

## Como compilar

O projeto usa Android Gradle Plugin 8.7.3, Gradle 8.9, compileSdk/targetSdk 35 e
exige JDK 17 ou superior. As instruções detalhadas de ambiente, assinatura e
instalação estão em [README-PDV-SMS.md](README-PDV-SMS.md). Os atalhos:

```bat
build.bat                :: gera o APK de depuração
build.bat release        :: gera o APK assinado (exige keystore.properties)
verificar-app.bat        :: confere dispositivo, app instalado e permissão de SMS
publicar-celular.bat     :: instala o APK no celular conectado por USB
criar-keystore.bat       :: cria o keystore da assinatura release
verificar-keystore.bat   :: confere a senha do keystore
```

## Segurança

- Nenhum keystore, senha ou arquivo `keystore.properties` faz parte deste
  repositório. Gere os seus com `criar-keystore.bat` e mantenha fora do Git.
- A chave de pareamento e o token da API ficam na pasta de dados do Gaspar, no
  perfil do usuário do Windows (ou em `~/.config/caracore/gaspar` no Linux).
- O celular cria o próprio par de chaves: a privada fica protegida pelo Android
  Keystore e nunca sai do aparelho; a pública vai ao Gaspar no pareamento. Cada
  pedido é fechado com a chave do celular (AES-256-GCM) e só vale para o `id`
  daquele pedido.
- Por cima, o tráfego na rede local vai cifrado com AES-256-GCM usando o segredo
  do pareamento. A rede ainda precisa ser confiável: o Gaspar só aceita pedidos
  da própria máquina e aplica limites de volume.
- O app não aceita acionamento por outros aplicativos e limita o envio a 300 SMS
  por dia no próprio aparelho.
- A partir da 1.7, o app **não lê SMS**: a licença Premium é digitada na tela ou
  vem no QR de configuração. O aviso de backup só é aceito quando traz o token
  gerado no próprio painel do celular (ver [README-PDV-SMS.md](README-PDV-SMS.md)).
- No código deste repositório, o Gaspar não guarda o número nem o texto: a
  auditoria e o histórico registram só metadados. O Gaspar **1.7.1** publicado
  já funciona assim. O **1.7.0** ainda grava o número completo e o texto no
  histórico local; o **1.7.1** é a versão recomendada.
  O termo completo está em
  [wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html).

## Limitações conhecidas

- O "entregue" depende da operadora devolver o recibo; quando ela não devolve,
  o pedido fica em "enviado", que já confirma que o SMS saiu do celular.
- A licença digitada confere formato e mês, sem assinatura digital.
- A confirmação de operações aparece como notificação normal: o celular precisa
  estar desbloqueado e o dono precisa tocar na notificação para abrir a tela.
  Não há mais tela cheia sobre a tela de bloqueio.
- O aviso de backup enviado pelo PDV só é aceito quando é endereçado ao app
  (`-p br.com.caracore.pdv.sms`) e traz o token mostrado no painel; sem isso o
  Android bloqueia o aviso ou o app o recusa. PDVs que ainda não enviam o token
  têm o aviso recusado até serem atualizados.
- O pareamento usa HTTP na rede local para o diagnóstico inicial; não há TLS.
- O SMS enviado fica na caixa **Enviadas** do aplicativo de mensagens, como
  qualquer SMS; o Gaspar não controla essa cópia.
- A 1.6 e a 1.7 foram exercitadas em emulador Android, mas ainda não em celular
  físico; o lado do computador da confirmação ainda não existe.
