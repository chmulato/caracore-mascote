# App Android - Enviar SMS

Este diretório guarda o aplicativo que roda no celular Android e dispara os SMS
pedidos pelo Gaspar. Ele é a outra metade da ponte local de SMS descrita em
[wiki.caracore.com.br/gaspar/sms.html](https://wiki.caracore.com.br/gaspar/sms.html).

> O código deste diretório corresponde ao **1.5**, já publicado na
> [Release Android 1.5](https://github.com/chmulato/caracore-mascote/releases/tag/android-v1.5).
> Ele abre o envelope cifrado, só aceita SMS de licença do número oficial
> configurado na tela e fecha o provedor de licença com `readPermission` de
> assinatura. O **1.4**, também publicado, não tem essa trava; instale o 1.5 por
> cima, com o mesmo certificado. O Gaspar **1.7.1** ou mais novo usa o 1.5; o
> aplicativo **1.2** só atende o Gaspar **1.7.0**.

## Para que serve

- Recebe um pedido **cifrado de ponta a ponta** vindo do computador na mesma
  rede Wi-Fi e abre com a chave que só ele tem.
- Envia o SMS diretamente pelo chip do celular, sem abrir a tela de mensagens.
- Devolve ao Gaspar o "aceito" do chip e o "entregue" da operadora.
- Responde na rede local para o Gaspar encontrar o aparelho automaticamente.
- Lê o QR de pareamento gerado pelo Gaspar para guardar a chave e o endereço.

O envio por cabo USB (ADB) foi **retirado**: a activity de envio não é mais
exportada e exige permissão interna de assinatura. O teste manual é feito pela
janela **Celular / SMS** do Gaspar.

## Como preparar o celular

1. Compile e instale o APK no aparelho (Android 7.0 ou superior).
2. Abra o aplicativo e conceda as permissões de SMS.
3. Desative a otimização de bateria para o app, para o serviço não ser encerrado.
4. Mantenha o celular e o computador na mesma rede Wi-Fi.
5. No Gaspar, abra a janela **Celular / SMS**, clique em **Parear celular** e leia o
   código com o aplicativo.

## Como compilar

O projeto usa Android Gradle Plugin 7.4.2, compileSdk 33 e JDK 11 ou superior.
As instruções detalhadas de ambiente, assinatura e instalação estão em
[README-PDV-SMS.md](README-PDV-SMS.md). Os atalhos:

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
- No código deste repositório, o Gaspar não guarda o número nem o texto: a
  auditoria e o histórico registram só metadados. O Gaspar **1.7.1** publicado
  já funciona assim. O **1.7.0** ainda grava o número completo e o texto no
  histórico local; o **1.7.1** é a versão recomendada.
  O termo completo está em
  [wiki.caracore.com.br/gaspar/privacidade.html](https://wiki.caracore.com.br/gaspar/privacidade.html).

## Limitações conhecidas

- O "entregue" depende da operadora devolver o recibo; quando ela não devolve,
  o pedido fica em "enviado", que já confirma que o SMS saiu do celular.
- A licença recebida por SMS confere formato e mês, sem assinatura digital.
- O `targetSdk` do projeto é 27; versões novas do Android podem encerrar o
  serviço em segundo plano e exigir reabrir o aplicativo.
- O pareamento usa HTTP na rede local para o diagnóstico inicial; não há TLS.
- O SMS enviado fica na caixa **Enviadas** do aplicativo de mensagens, como
  qualquer SMS; o Gaspar não controla essa cópia.
