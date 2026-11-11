# Ambiente Black-Box - Soberania do Código

Guia da Cara Core Informática para reduzir telemetria no ambiente de desenvolvimento e impedir que domínios conhecidos de coleta saiam do equipamento sem permissão expressa.

O bloqueio é feito pelo **Gaspar BlackBox**, que grava um bloco delimitado no arquivo `hosts` do sistema. O processo é reversível e não instala serviços.

## 1. Configurações do editor

Arquivos:

- Cursor: `%APPDATA%\Cursor\User\settings.json`
- VS Code: `%APPDATA%\Code\User\settings.json`

Chaves recomendadas:

```json
{
  "telemetry.telemetryLevel": "off",
  "telemetry.enableCrashReporter": false,
  "enable-crash-reporter": false
}
```

| Chave | Efeito |
| --- | --- |
| `telemetry.telemetryLevel` | Desativa telemetria de uso, erros e eventos. |
| `telemetry.enableCrashReporter` | Desativa o envio de relatórios de crash. |
| `enable-crash-reporter` | Reforça a desativação no Electron. |
| `update.mode` | Opcional: `"none"` evita busca automática de atualizações. |
| `extensions.autoCheckUpdates` | Opcional: `false` evita consulta automática de extensões. |
| `extensions.autoUpdate` | Opcional: `false` evita atualização automática de extensões. |

No Cursor, ative também **Settings > General > Privacy Mode**. Isso reduz a retenção de prompts e código por provedores de modelo. Se a versão atual expuser a chave, use `"cursor.privacyMode": true`.

Reinicie o editor depois de alterar. Desligar a telemetria no editor não impede todos os DNS lookups; para bloquear de fato, use o arquivo `hosts`.

## 2. Extensões que costumam enviar dados

| Extensão ou família | O que costuma enviar | Como limitar |
| --- | --- | --- |
| GitHub Copilot | Trechos de código e contexto | Desative em repositórios sensíveis; use modelos locais quando possível. |
| GitLens | Uso e telemetria | `"gitlens.telemetry.enabled": false` |
| Red Hat (Java, YAML etc.) | Telemetria de uso | `"redhat.telemetry.enabled": false` |
| Docker | Telemetria e analytics | Desative nas configurações da extensão. |
| Azure / MS SQL | Telemetria e diagnóstico | Desative a telemetria de cada extensão. |
| Codeium, Tabnine e similares | Contexto de código para servidores | Não instale ou desative em ambiente black-box. |
| Extensões de IA em nuvem | Código e prompts | Prefira modelos locais, como Ollama. |

Boas práticas:

- Revise cada extensão em **Details** e procure por Telemetry, Data e Privacy.
- Desative telemetria específica quando existir configuração própria.
- Mantenha o mínimo de extensões em projetos sensíveis.

## 3. Bloqueio no arquivo hosts

### Pela interface

1. Abra o painel do Gaspar.
2. Clique em **BlackBox**.
3. Aceite a elevação (UAC no Windows, `pkexec` no Linux).
4. Clique em **Aplicar bloqueio**.
5. Opcionalmente, clique em **Atualizar cache DNS**.

O status mostra **Bloqueio ativo** ou **Bloqueio inativo**. O botão **Remover bloqueio** restaura o conteúdo anterior.

### Pela linha de comando

```bash
python -m gaspar.telemetry_hosts --status
python -m gaspar.telemetry_hosts --dry-run
python -m gaspar.telemetry_hosts --remove
```

O `--dry-run` mostra o que seria feito sem escrever no arquivo e sem exigir administrador.

### O que é gravado

```text
# BLOCK TELEMETRIA - INICIO (Cara Core Black-Box)
0.0.0.0 vortex.data.microsoft.com
0.0.0.0 vortex-win.data.microsoft.com
...
# BLOCK TELEMETRIA - FIM
```

Características:

- 34 domínios conhecidos de telemetria da Microsoft, VS Code/Cursor, Azure e Application Insights.
- Reaplicar é idempotente: o bloco anterior é substituído, não duplicado.
- A remoção preserva o restante do arquivo e o estilo de quebra de linha (CRLF ou LF).
- O cache DNS é atualizado por `ipconfig`, `resolvectl`, `systemd-resolve` ou `nscd`, conforme disponível.
- Requer privilégios de administrador/root para escrever no arquivo.

### Efeitos colaterais possíveis

O bloqueio inclui domínios de autenticação e marketplace:

- `login.microsoftonline.com`
- `vscode.dev`
- `marketplace.visualstudio.com`
- `management.azure.com`
- `global.azure.microsoft.com`
- `monitor.azure.com`

Enquanto o bloqueio estiver ativo, login Microsoft, instalação de extensões e alguns recursos do Azure podem falhar. Remova o bloqueio antes de autenticar ou instalar extensões.

## 4. Firewall do Windows e Ollama

### Ollama em localhost:11434

O tráfego para `127.0.0.1:11434` é loopback e normalmente já é permitido pelo Firewall do Windows. Na maioria dos casos não é necessário criar regra.

Só crie uma regra de entrada para a porta 11434 se o Ollama estiver vinculado a `0.0.0.0` e você quiser acesso explícito.

### Bloquear telemetria sem quebrar o ambiente

Não bloqueie a porta 443 inteira para o editor: isso quebra atualizações, extensões, Git e outros serviços. A abordagem prática é:

1. Bloquear os domínios de telemetria pelo arquivo `hosts`.
2. Desligar a telemetria nas configurações do editor e das extensões.
3. Usar regras de firewall por processo apenas se houver uma política adicional.

Regras por IP de destino exigem manter uma lista de IPs que muda com frequência. O bloqueio por nome de host via `hosts` é mais simples e previsível.

## 5. Checklist rápido

- `telemetry.telemetryLevel` em `"off"`.
- `telemetry.enableCrashReporter` e `enable-crash-reporter` em `false`.
- Cursor com Privacy Mode ativado.
- Telemetria de extensões desligada (GitLens, Red Hat, Docker etc.).
- Evitar extensões de IA em nuvem em projetos da Cara Core.
- Bloqueio aplicado pelo Gaspar BlackBox e cache DNS atualizado.
- Ollama em `localhost:11434` para modelos locais.
- Opcional: `update.mode` em `"none"` e atualizações automáticas de extensões desligadas.
- Remover o bloqueio antes de login Microsoft, marketplace ou operações do Azure.

Soberania do Código - Cara Core Informática. Nada sai do equipamento sem sua permissão expressa.
