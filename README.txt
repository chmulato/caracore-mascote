MASCOTEAPP
==========

Aplicativo para simular atividade no computador e manter o status ativo em aplicacoes como Microsoft Teams. Inclui a variante Mascote BlackBox para bloqueio de telemetria na rede.


DESCRICAO
---------

O MascoteApp e uma ferramenta que automatiza movimentos do mouse e pressiona teclas periodicamente para evitar que o sistema seja marcado como "ausente" em aplicativos de comunicacao corporativa. O aplicativo possui interface grafica intuitiva com mascote animado e sistema de logs detalhado.

O Mascote BlackBox e uma versao que roda como Administrador e bloqueia dominios de telemetria (Microsoft, VS Code, Cursor, Azure, etc.) no arquivo hosts do Windows, com interface grafica para aplicar/remover bloqueio e atualizar o DNS.


FUNCIONALIDADES
----------------

MascoteApp (mascote.exe)
  - Movimentacao aleatoria e natural do mouse com multiplos algoritmos
  - Simulacao de pressionamento de teclas (barra de espaco)
  - Tentativa de manter Microsoft Teams ativo
  - Interface grafica com mascote animado (GIF)
  - Configuracao de intervalos entre acoes (padrao: 5 minutos)
  - Sistema de logs detalhado em arquivo (cycle_log.txt)
  - Som opcional a cada ciclo executado
  - Tratamento robusto de erros
  - Compilacao para executavel Windows

Mascote BlackBox (mascote_blackbox.exe)
  - Bloqueio de telemetria via arquivo hosts (rede)
  - Execucao como Administrador (UAC)
  - Interface para aplicar / remover bloqueio e atualizar DNS (flush)
  - Compilacao para executavel com solicitacao de admin


REQUISITOS DO SISTEMA
---------------------

  - Windows 7/8/10/11
  - Python 3.7 ou superior
  - Resolucao minima: 800x600 pixels


DEPENDENCIAS
------------

  - Python 3.x (tkinter incluido)
  - Pillow >= 10.0.0 (manipulacao de imagens)
  - pyautogui >= 0.9.54 (automacao de interface)
  - PyInstaller >= 6.0.0 (compilacao para executavel)


INSTALACAO E EXECUCAO
---------------------

Metodo 1: Executar com Python

  1. Clone ou baixe este repositorio
  2. Instale as dependencias:
       pip install -r requirements.txt
       (Se pip nao for reconhecido: python -m pip install -r requirements.txt
        ou execute instalar_dependencias.bat)
  3. Execute o aplicativo:
       python mascote.py

Metodo 2: Arquivo Batch (Windows)

  Execute o arquivo executar_mascote.bat com duplo clique.

Mascote BlackBox (bloqueio de telemetria)

  1. Execute como Administrador (necessario para editar o arquivo hosts).
  2. Ou use executar_mascote_blackbox.bat (clique direito, Executar como administrador).
  3. Na interface: Aplicar bloqueio; em seguida Atualizar DNS (flush) se desejar.


COMPILACAO PARA EXECUTAVEL
---------------------------

Compilacao Automatica

  Comando                              Resultado
  python mascote_exe.py                Gera apenas mascote.exe
  python mascote_exe.py --blackbox      Gera apenas mascote_blackbox.exe
  python mascote_exe.py --all          Gera mascote.exe e mascote_blackbox.exe

  Ou use os arquivos batch:
  - compilar_mascote.bat         compila o MascoteApp
  - compilar_mascote_blackbox.bat compila o Mascote BlackBox

Compilacao Manual

  1. Instale PyInstaller (use python -m pip se pip nao for reconhecido):
       python -m pip install pyinstaller

  2. MascoteApp:
       pyinstaller --onefile --windowed --name mascote --icon mascote.ico mascote.py

  3. Mascote BlackBox (com UAC admin):
       pyinstaller --noconfirm mascote_blackbox.spec

  4. Executaveis em dist/mascote.exe e dist/mascote_blackbox.exe

Limpar pasta dist/build

  Para remover os artefatos de compilacao antes de recompilar:
    python limpar_dist.py              Remove apenas dist/
    python limpar_dist.py --build      Remove dist/ e build/
    python limpar_dist.py -n           Simula, nao remove (dry-run)

Distribuicao

  - MascoteApp: copie o conteudo de dist/ (incluindo GIF e icones) e execute mascote.exe.
  - Mascote BlackBox: copie dist/mascote_blackbox.exe; execute como Administrador para aplicar o bloqueio de telemetria.


CONFIGURACAO E USO
------------------

Interface Principal

  - Campo Intervalo: configure o tempo entre acoes em segundos.
  - Botao Ativar/Desativar: inicia ou para o ciclo automatico.
  - Checkbox Som: ativa ou desativa som a cada ciclo.
  - Contador: mostra proximo movimento e ciclos executados.

Funcionamento

  O aplicativo executa as seguintes acoes a cada intervalo:

  1. Movimento do Mouse: cinco tipos de movimento aleatorio (micro, pequeno, medio, circular, area aleatoria).
  2. Simulacao de Tecla: pressiona barra de espaco.
  3. Ativacao do Teams: tenta manter o aplicativo ativo.
  4. Sequencias Multiplas: 10% das vezes executa 2-4 movimentos consecutivos.

Sistema de Logs

  Todos os eventos sao registrados em cycle_log.txt:
  - Inicializacao e encerramento da aplicacao
  - Configuracoes alteradas pelo usuario
  - Detalhes de cada ciclo executado
  - Tipos de movimento e coordenadas
  - Erros e excecoes tratadas


DOCUMENTACAO
------------

  README.txt                      Este arquivo (visao geral e uso do projeto)
  PIP_CONFIGURACAO.txt            Pip nao reconhecido: usar python -m pip e PATH
  BLACKBOX_AMBIENTE_DESENVOLVIMENTO.txt  Ambiente black-box, telemetria, hosts, firewall


ESTRUTURA DO PROJETO
--------------------

  mascote_py/
    mascote.py                   Aplicativo principal (manter ativo Teams)
    mascote_blackbox.py          Bloqueio de telemetria (hosts, requer admin)
    block-telemetry-hosts.py     Script CLI para bloqueio (sem GUI)
    mascote_exe.py               Script de compilacao (mascote + blackbox)
    mascote.spec                 Spec PyInstaller (MascoteApp)
    mascote_blackbox.spec        Spec PyInstaller (BlackBox, UAC admin)
    executar_mascote.bat         Executar MascoteApp com Python
    executar_mascote_blackbox.bat Executar BlackBox com Python
    compilar_mascote.bat         Compilar mascote.exe
    compilar_mascote_blackbox.bat Compilar mascote_blackbox.exe
    instalar_dependencias.bat    Instala requirements (use se pip nao for reconhecido)
    limpar_dist.py               Remove dist/ e opcionalmente build/
    requirements.txt             Dependencias Python
    PIP_CONFIGURACAO.txt         Como configurar pip quando nao e reconhecido
    BLACKBOX_AMBIENTE_DESENVOLVIMENTO.txt  Guia ambiente black-box
    mascote.gif                  Animacao do mascote
    mascote.ico                  Icone do aplicativo
    boneco.ico                   Icone alternativo
    cycle_log.txt                Logs (gerado em runtime)
    LICENSE                      Licenca MIT
    README.txt                   Esta documentacao


ALGORITMOS DE MOVIMENTO
-----------------------

  - Micro Movement: ajustes finos de 1-5 pixels.
  - Small Movement: movimentos tipicos de 10-30 pixels.
  - Medium Movement: navegacao entre elementos de 50-100 pixels.
  - Circular Movement: trajetorias curvas com pontos intermediarios.
  - Random Corner: movimento para areas aleatorias da tela.


TRATAMENTO DE ERROS
-------------------

  - Operacoes do Teams sao opcionais e nao interrompem a simulacao
  - Verificacao de limites da tela antes de movimentar o mouse
  - Logs detalhados para diagnostico de problemas
  - Continuidade garantida mesmo com falhas parciais


SOLUCAO DE PROBLEMAS
--------------------

Aplicativo nao inicia
  - Verifique se Python 3.x esta instalado
  - Instale as dependencias: pip install -r requirements.txt (ou python -m pip install -r requirements.txt / instalar_dependencias.bat)
  - Verifique se os arquivos GIF e icones estao presentes

Executavel nao funciona
  - Mantenha todos os arquivos da pasta dist/ juntos
  - Adicione excecao no antivirus se necessario
  - Execute pelo terminal para ver mensagens de erro
  - Se aparecer "ModuleNotFoundError: No module named 'pyautogui'", recompile com: python mascote_exe.py (o script ja inclui os modulos necessarios no exe)

Teams nao fica ativo
  - Ajuste a posicao do icone na funcao click_on_teams_icon
  - Verifique se o Teams esta instalado e visivel
  - O aplicativo continua funcionando mesmo sem o Teams


SEGURANCA E PRIVACIDADE
-----------------------

  - Nao coleta dados pessoais ou corporativos
  - Funciona apenas localmente no computador
  - Logs contem apenas informacoes tecnicas de funcionamento
  - Codigo fonte aberto para auditoria


LICENCA
-------

  Este projeto esta licenciado sob a Licenca MIT. Consulte o arquivo LICENSE para detalhes.


AUTOR
-----

  Christian Vladimir Uhdre Mulato
  Campo Largo, Parana - Brasil
  Outubro de 2025


HISTORICO DE VERSOES
--------------------

  - v1.0: Versao inicial com movimentacao basica.
  - v1.1: Sistema de logs e tratamento de erros.
  - v1.2: Algoritmos avancados de movimento.
  - v1.3: Compilacao automatica e documentacao completa.
  - v1.4: Mascote BlackBox (bloqueio de telemetria via hosts); compilacao --all e --blackbox.
  - v1.5: Documentacao somente em TXT; instalar_dependencias.bat e PIP_CONFIGURACAO.txt; limpar_dist.py; hidden-imports no exe (pyautogui/PIL); correcao encoding no compilador.
