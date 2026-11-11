# App Android - Enviar SMS

Este diretório guarda o aplicativo que roda no celular Android e dispara os SMS
pedidos pelo Gaspar. Ele é a outra metade da ponte local de SMS descrita em
[../docs/sms.md](../docs/sms.md).

## Para que serve

- Recebe um pedido cifrado vindo do computador na mesma rede Wi-Fi.
- Envia o SMS diretamente pelo chip do celular, sem abrir a tela de mensagens.
- Responde na rede local para o Gaspar encontrar o aparelho automaticamente.
- Lê o QR de pareamento gerado pelo Gaspar para guardar a chave e o endereço.

O envio por cabo USB (ADB) continua existindo como caminho de contingência do
PDV, mas a integração com o mascote usa a rede local.

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
- O tráfego na rede local vai cifrado com AES-256-GCM. A rede ainda precisa ser
  confiável: qualquer aparelho com a chave consegue pedir envios, por isso o
  Gaspar aplica limite de volume e o celular deve ficar em rede protegida.

## Limitações conhecidas

- O aplicativo confirma que o SMS foi entregue ao chip, mas ainda não devolve o
  recibo de entrega da operadora. O Gaspar mostra "entregue ao celular".
- A licença recebida por SMS confere formato e mês, sem assinatura digital.
- O `targetSdk` do projeto é 27; versões novas do Android podem encerrar o
  serviço em segundo plano e exigir reabrir o aplicativo.
- O pareamento usa HTTP na rede local para o diagnóstico inicial; não há TLS.
