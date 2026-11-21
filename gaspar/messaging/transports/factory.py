"""A fabrica que transforma o ``messaging.json`` em motoristas vivos.

Ate aqui, nenhum codigo do produto construia um motorista: a fila sabia o nome
escolhido por origem, mas nao tinha como montar o que existia por traz do nome.
Esta pagina fecha esse buraco e concentra as regras que precisam ficar juntas:

* **o que tem codigo**: os nomes que a fabrica sabe montar. ``usb_modem`` ja tem
  nome na RFC, mas ainda nao tem motorista, e recusa com esse motivo em vez de um
  generico;
* **o que nao pode ir em claro**: a senha da caixa postal e o segredo do pareamento
  entram no arquivo selados pelo cofre da fila (``Vault.seal``). Achando texto
  aberto no bloco, o motorista nao e montado e a origem fica desligada - aceitar
  em claro sem reclamar seria o caminho para o segredo morar para sempre no disco;
* **onde a ponte guarda o que aprendeu**: sem caminho dito no arquivo, o estado da
  ponte de e-mail vai para a pasta de dados do mascote, nunca para o diretorio de
  trabalho de quem abriu o Gaspar.

Nada aqui abre conexao: montar e ler ajuste e abrir selo. A rede aparece quando a
fila pede um envio, e so para o motorista que alguma origem escolheu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from gaspar.messaging.errors import MessagingError, StorageError
from gaspar.messaging.transport import SmsTransportDriver
from gaspar.messaging.vault import Vault

from ..config import _as_bool
from .android_lan import NOME_MOTORISTA as NOME_ANDROID_LAN
from .android_lan import AndroidLanTransportDriver, LanSettings
from .loopback import LoopbackTransportDriver
from .smtp_email import EmailBridgeDriver, EmailSettings

NOME_LOOPBACK = LoopbackTransportDriver.name
NOME_EMAIL = EmailBridgeDriver.name

#: o arquivo de ajustes do estado da ponte de e-mail, quando o bloco nao diz onde
ARQUIVO_ESTADO_EMAIL = "bridge-smtp.state"

#: nomes que a RFC ja anunciava, mas que ainda nao tem codigo para montar
MEIOS_SEM_CODIGO: dict[str, str] = {
    "usb_modem": "o motorista do modem USB ainda nao foi escrito",
}

#: campos que so podem aparecer no arquivo com o sufixo ``_sealed``
CAMPOS_EM_CLARO: dict[str, tuple[str, ...]] = {
    NOME_ANDROID_LAN: ("segredo", "segredos_por_origem"),
    NOME_EMAIL: ("password", "bridge_key"),
}

#: motorista -> {campo selado no arquivo -> campo aberto no objeto em memoria}
CAMPOS_SELADOS: dict[str, dict[str, str]] = {
    NOME_ANDROID_LAN: {
        "segredo_sealed": "segredo",
        "segredos_por_origem_sealed": "segredos_por_origem",
    },
}

#: o que a fabrica monta, em ordem para caber em uma frase de ajuda
NOMES_MONTAVEIS: tuple[str, ...] = (NOME_ANDROID_LAN, NOME_LOOPBACK, NOME_EMAIL)


class MotoristaNaoMontavel(MessagingError):
    """O bloco do arquivo nao da para montar o motorista - e o motivo e dito."""


def nomes_disponiveis() -> tuple[str, ...]:
    return NOMES_MONTAVEIS


def construir(
    nome: str,
    ajustes: object = None,
    *,
    vault: Vault | None = None,
    home: Path | str | None = None,
) -> SmsTransportDriver:
    """Monta um motorista a partir do bloco de ajustes dele no arquivo.

    Os ajustes vem como vieram do ``messaging.json``: o que a fabrica nao conhece
    fica de fora, e o que e segredo so entra selado.
    """
    nome = str(nome or "").strip()
    corpo = ajustes if isinstance(ajustes, dict) else {}
    if nome in MEIOS_SEM_CODIGO:
        raise MotoristaNaoMontavel(MEIOS_SEM_CODIGO[nome])
    if nome == NOME_LOOPBACK:
        return _montar_loopback(corpo)
    if nome == NOME_EMAIL:
        return _montar_email(corpo, vault=vault, home=home)
    if nome == NOME_ANDROID_LAN:
        return _montar_android_lan(corpo, vault=vault)
    ajuda = ", ".join(NOMES_MONTAVEIS)
    raise MotoristaNaoMontavel(f"meio desconhecido: {nome or '(vazio)'}; sei montar {ajuda}")


def montar_registry(
    registry,
    config: object,
    *,
    vault: Vault | None = None,
    home: Path | str | None = None,
    log: Callable[[str], None] | None = None,
) -> list[str]:
    """Registra todo motorista que alguma origem escolheu. Retorna os nomes montados.

    Um bloco recusado nao derruba a barra: o motorista fica de fora, a origem que o
    escolheu fica desligada e o motivo vai para o log. Assim um erro de digitacao no
    arquivo do Hub nao tira o PDV do ar.
    """
    citados = tuple(getattr(config, "meios_citados", ()) or ())
    registrados: list[str] = []
    for nome in citados:
        if nome in registry.names():
            continue
        ajustes = getattr(config, "settings_for", dict)(nome)
        try:
            registry.register(construir(nome, ajustes, vault=vault, home=home))
        except MotoristaNaoMontavel as exc:
            _logar(log, f"meio '{nome}' nao montado: {str(exc)[:220]}")
            continue
        registrados.append(nome)
    return registrados


# --------------------------------------------------------------------- internos


def _montar_loopback(corpo: dict) -> LoopbackTransportDriver:
    """Meio de bancada: grava o pedido em memoria e nao envia nada para a rua."""
    dispositivo = str(corpo.get("dispositivo") or "").strip() or "loopback-0"
    disponivel = _as_bool(corpo.get("disponivel", True), True)
    return LoopbackTransportDriver(device_id=dispositivo, available=disponivel)


def _montar_email(corpo: dict, *, vault: Vault | None, home: Path | str | None) -> EmailBridgeDriver:
    recusar_segredo_em_claro(NOME_EMAIL, corpo)
    settings = EmailSettings.from_dict(corpo)
    if not settings.state_path and home is not None:
        settings.state_path = str(Path(home) / ARQUIVO_ESTADO_EMAIL)
    return EmailBridgeDriver(settings, vault=vault)


def _montar_android_lan(corpo: dict, *, vault: Vault | None) -> AndroidLanTransportDriver:
    recusar_segredo_em_claro(NOME_ANDROID_LAN, corpo)
    settings = LanSettings.from_dict(_abrir_selados(NOME_ANDROID_LAN, corpo, vault))
    return AndroidLanTransportDriver(settings)


def recusar_segredo_em_claro(nome: str, corpo: dict) -> None:
    """Nada de segredo aberto no arquivo: o bloco e recusado com o campo no nome."""
    proibidos = [campo for campo in CAMPOS_EM_CLARO.get(nome, ()) if corpo.get(campo)]
    if proibidos:
        selados = ", ".join(f"{campo}_sealed" for campo in proibidos)
        raise MotoristaNaoMontavel(
            f"o bloco traz {', '.join(proibidos)} em claro; grave selado pelo cofre da fila ({selados})"
        )


def _abrir_selados(nome: str, corpo: dict, vault: Vault | None) -> dict:
    """Troca campo selado por campo aberto, so em memoria. O arquivo nao muda."""
    aberto = dict(corpo)
    for campo_selado, campo_aberto in CAMPOS_SELADOS.get(nome, {}).items():
        if campo_selado not in aberto:
            continue
        aberto[campo_aberto] = _abrir(vault, aberto.pop(campo_selado), campo_aberto)
    return aberto


def _abrir(vault: Vault | None, valor: object, campo: str) -> object:
    if vault is None:
        raise MotoristaNaoMontavel(f"{campo} esta selado, mas nao ha cofre da fila para abri-lo")
    try:
        if isinstance(valor, dict):
            return {chave: vault.open(item) for chave, item in valor.items()}
        return vault.open(str(valor or ""))
    except (StorageError, ValueError, TypeError, UnicodeDecodeError):
        # O motivo cita o campo, nunca o conteudo: quem le o log nao ve segredo.
        raise MotoristaNaoMontavel(
            f"{campo} selado nao abriu com a chave desta maquina; pareie de novo ou resele"
        )


def _logar(log: Callable[[str], None] | None, mensagem: str) -> None:
    if log is None:
        return
    try:
        log(mensagem)
    except Exception:
        pass
