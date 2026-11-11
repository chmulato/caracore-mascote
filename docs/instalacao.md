# Instalação do Gaspar e do aplicativo do celular

Este guia leva você do zero até o primeiro SMS de teste. Ele foi escrito para
quem instala o sistema na loja, sem detalhes de programação. Os detalhes
técnicos ficam em [tecnico.md](tecnico.md).

> **Antes de tudo:** a ponte de SMS está no código-fonte. Os instaladores 1.6.0
> já publicados **não** a incluem. Para usar o SMS hoje, você tem dois caminhos:
>
> 1. **Rodar o Gaspar a partir do código**, que já tem a ponte
>    ([guia técnico](tecnico.md#rodar-a-partir-do-código)); ou
> 2. **Gerar um instalador novo** na máquina de build
>    ([guia técnico](tecnico.md#build-no-windows)).
>
> A Parte 1 abaixo instala o mascote com o instalador 1.6.0. Ela serve para
> quem vai usar só o mascote ou como referência do assistente; para o SMS, use
> um dos dois caminhos acima.

## Antes de começar

Confira se você tem:

- [ ] Um computador com **Windows 10/11** ou **Linux com X11/XWayland**.
- [ ] Um celular **Android 7.0 ou superior**, com chip e crédito para SMS.
- [ ] Celular e computador na **mesma rede Wi-Fi** (não use rede de visitante).
- [ ] Os arquivos da tabela de artefatos abaixo.
- [ ] Acesso de administrador apenas no computador, para instalar o Gaspar.

## Artefatos necessários

| Arquivo | Para que serve | Como obter |
| --- | --- | --- |
| `GasparSetup-1.6.0.exe` | Instalar o Gaspar no Windows | [Baixar](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/GasparSetup-1.6.0.exe) |
| `gaspar_1.6.0_amd64.deb` | Instalar o Gaspar em Debian, Ubuntu, Mint e derivados | [Baixar](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/gaspar_1.6.0_amd64.deb) |
| `Gaspar-1.6.0-amd64.AppImage` | Usar o Gaspar em outras distribuições Linux, sem instalar | [Baixar](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/Gaspar-1.6.0-amd64.AppImage) |
| `SHA256SUMS.txt` | Conferir se o download chegou completo (opcional) | [Baixar](https://github.com/chmulato/caracore-mascote/releases/download/v1.6.0/SHA256SUMS.txt) |
| `pdv-sms-enviar-1.0.apk` (teste) ou `pdv-sms-enviar-1.0-release.apk` (assinado) | Instalar o aplicativo que envia os SMS no celular | Não está no repositório. É gerado a partir da pasta `android/`; veja [android/README-PDV-SMS.md](../android/README-PDV-SMS.md). Se a Cara Core entregar o APK pronto, use esse arquivo. |
| `keystore.properties` + arquivo `.keystore` | Assinar uma versão nova do aplicativo do celular | Criados na máquina de build com `criar-keystore.bat`. **Nunca** compartilhe nem publique esses arquivos. |

Todos os downloads do Gaspar ficam na página da
[Release 1.6.0](https://github.com/chmulato/caracore-mascote/releases/tag/v1.6.0).

## Parte 1 - Instalar o Gaspar no computador

### Windows 10 ou 11

1. Baixe `GasparSetup-1.6.0.exe`.
2. Dê dois cliques e siga o assistente: **Avançar**, **Instalar**, **Concluir**.
3. Abra o Gaspar pelo atalho da Área de Trabalho ou pelo menu Iniciar.
4. Na primeira vez, o painel de configuração abre junto. Ajuste o que quiser e
   clique em **Ocultar** para deixar só o mascote na tela.
5. Para encerrar de verdade, clique com o botão direito no ícone perto do
   relógio e escolha **Sair**.

Se o Windows mostrar o aviso azul do SmartScreen, clique em **Mais informações**
e depois em **Executar assim mesmo**. O programa não é assinado digitalmente;
isso é esperado em programas distribuídos diretamente pela Cara Core.

### Linux - Debian, Ubuntu, Mint e derivados

1. Baixe `gaspar_1.6.0_amd64.deb`.
2. Dê dois cliques e instale pelo aplicativo de pacotes, ou use o terminal:

   ```bash
   sudo apt install ./gaspar_1.6.0_amd64.deb
   ```

3. Abra **Gaspar** pelo menu de aplicativos, ou digite `gaspar` no terminal.
4. O **Gaspar BlackBox** aparece no mesmo menu.

### Linux - qualquer distribuição, sem instalar

1. Baixe `Gaspar-1.6.0-amd64.AppImage`.
2. Clique com o botão direito, abra **Propriedades**, vá em **Permissões** e
   marque **Permitir executar**.
3. Dê dois cliques no arquivo.

O Gaspar precisa de uma sessão **X11 ou XWayland**. Em Wayland puro, o mascote
pode aparecer com um fundo quadrado e o clique pode não atravessar.

### Conferir se abriu

O mascote deve aparecer flutuando em um canto da tela e o ícone do Gaspar deve
ficar perto do relógio. Se nada aparecer, veja **Problemas comuns** no fim
deste guia.

## Parte 2 - Instalar o aplicativo no celular

O aplicativo é o que dispara o SMS pelo chip. Ele não precisa de internet; usa
a Wi-Fi da loja para conversar com o Gaspar.

1. **Obtenha o APK** (`pdv-sms-enviar-1.0.apk` ou
   `pdv-sms-enviar-1.0-release.apk`):
   - se a Cara Core entregou o arquivo, use-o;
   - para gerar a partir do código, siga
     [android/README-PDV-SMS.md](../android/README-PDV-SMS.md). É preciso um
     computador com JDK 11 ou superior e o Android SDK instalado.
2. **Envie o APK para o celular** por cabo USB, WhatsApp, Telegram ou Google
   Drive.
3. **Abra o arquivo no celular** e toque em **Instalar**. Se aparecer o aviso de
   "fontes desconhecidas", autorize apenas para esta instalação.
4. Se o Play Protect avisar que não reconhece o aplicativo, escolha
   **Instalar mesmo assim**. O APK não vem da Play Store.
5. **Abra o aplicativo** e conceda as permissões de SMS quando forem pedidas:
   - enviar SMS;
   - receber SMS;
   - ler SMS.
6. **Desative a otimização de bateria** para este aplicativo. Sem isso, o
   Android pode encerrar o serviço e o celular para de responder ao Gaspar.
   No Android 7 a 12, o caminho costuma ser **Configurações > Aplicativos >
   [nome do app] > Bateria > Sem restrições**. Em versões mais novas, procure
   por "bateria" nas configurações do aplicativo.
7. Deixe o celular conectado na **mesma Wi-Fi** do computador e mantenha o
   aplicativo aberto durante a configuração.

## Parte 3 - Parear o celular com o Gaspar

1. No computador, abra o Gaspar e clique em **Celular / SMS**.
2. Marque **Ponte ativa**.
3. Clique em **Parear celular**. Um QR aparece em uma janela separada.
4. No celular, abra o aplicativo e use a leitura de QR.
5. Aponte para o código. O celular envia o diagnóstico e o Gaspar mostra
   **Celular pareado**.
6. Clique em **Enviar teste**, informe um número com DDD e confirme que o SMS
   chega ao aparelho de teste.

O QR vale por **15 minutos** e só pode ser usado **uma vez**. Se expirar, clique
em **Parear celular** de novo.

Se o celular não for encontrado, clique em **Procurar celular** e confira se os
dois aparelhos estão na mesma rede.

## Parte 4 - Ligar o PDV

O responsável pelo PDV precisa copiar, da janela **Celular / SMS**:

- o **endereço** mostrado em **Integração com o PDV** (por exemplo,
  `http://192.168.0.10:8766/api/sms`);
- o **token** da API.

Com esses dois dados, o PDV passa a pedir os SMS ao Gaspar. Os detalhes de
programação estão em [tecnico.md](tecnico.md#api-para-o-pdv), e o
comportamento do dia a dia está em [sms.md](sms.md).

## Checklist final

- [ ] O Gaspar abre e o mascote aparece na tela.
- [ ] O aplicativo do celular está instalado e com as permissões de SMS.
- [ ] Celular e computador estão na mesma Wi-Fi.
- [ ] O celular aparece como **pareado** na janela **Celular / SMS**.
- [ ] O **Enviar teste** chegou ao aparelho de teste.
- [ ] O PDV recebeu o endereço e o token da API.

## Atualizar

- **Gaspar no Windows:** baixe o instalador novo e execute por cima. Suas
  preferências são mantidas.
- **Gaspar no Linux:** instale o `.deb` novo com `sudo apt install ./arquivo.deb`
  ou substitua o AppImage.
- **Aplicativo do celular:** instale o APK novo por cima do antigo. O pareamento
  é mantido; se o QR mudar, refaça o pareamento.

## Desinstalar

- **Windows:** **Aplicativos instalados** > **Gaspar - Mascote Cara Core** >
  **Desinstalar**.
- **Linux `.deb`:** `sudo apt remove gaspar`.
- **AppImage:** apague o arquivo.
- **Celular:** toque e segure o ícone do aplicativo > **Desinstalar**.

Os dados ficam no computador em `%APPDATA%\CaraCore\Gaspar\` (Windows) ou
`~/.config/caracore/gaspar/` (Linux). Apague essa pasta se quiser remover tudo.

## Se algo der errado

| Situação | O que fazer |
| --- | --- |
| SmartScreen bloqueou o instalador | **Mais informações** > **Executar assim mesmo**. |
| O mascote não aparece no Linux | Use uma sessão X11/XWayland. Em Wayland puro o recorte não funciona. |
| O celular não instala o APK | Autorize "fontes desconhecidas" e, se o Play Protect bloquear, escolha instalar mesmo assim. |
| O celular não aparece em **Procurar celular** | Mesma Wi-Fi, aplicativo aberto, bateria otimizada desativada e firewall liberando o Gaspar em rede privada. |
| O QR expirou | Clique em **Parear celular** para gerar outro. |
| O SMS de teste não chega | Confira chip, crédito e permissão de SMS no celular. O estado **enviado** no Gaspar significa "entregue ao celular". |

Mais casos estão em [sms.md](sms.md#problemas-comuns).
