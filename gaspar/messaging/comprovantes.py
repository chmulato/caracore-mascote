"""A volta do SMS: o recibo que o celular devolve vira estado na fila.

A ida ja esta no motorista ``android_lan`` - ele entrega o pedido ao celular e o
aparelho, ao terminar, faz um POST cifrado para a porta que ja conhecia da 1.7.
Este modulo e o unico ponto que junta as duas pontas: manda o recibo para o
motorista registrado, procura o pedido na fila de cada origem e escreve o estado.

Nada aqui reenvia. Um recibo que nao abre, que nao aponta para pedido desta fila
ou que chega tarde demais para mudar alguma coisa e respondido sem efeito.
"""

from __future__ import annotations

from .model import (
    ORIGENS,
    STATUS_ENTREGUE,
    STATUS_ENVIADO,
    STATUS_FALHOU,
    STATUS_TERMINAIS,
)

MOTIVO_COMPROVANTE = "comprovante do celular"

#: os unicos estados que um comprovante pode afirmar sobre um pedido
ESTADOS_DE_COMPROVANTE: frozenset[str] = frozenset({STATUS_ENVIADO, STATUS_ENTREGUE, STATUS_FALHOU})


def aplicar_comprovante(store, registry, corpo: object, *, log=None) -> bool:
    """Abre o recibo cifrado e escreve o que ele diz na fila. False = nao e daqui.

    A porta 1.7 usa o mesmo caminho para decidir se cuida do recibo: enquanto a
    fila 2.0 nao reconhece o pedido, o recibo segue para a loja de antes.
    """
    referencia, estado, motorista = _abrir(registry, corpo)
    if not referencia:
        return False
    message = _procurar(store, referencia)
    if message is None:
        _log(log, f"comprovante de um pedido que nao esta na barra de mensagens: {referencia[:24]}")
        return False
    if estado not in ESTADOS_DE_COMPROVANTE or message.status == estado:
        return True
    if message.status in STATUS_TERMINAIS:
        _log(log, f"comprovante ignorado: o pedido {message.id} ja estaba fechado")
        return True
    store.mark(
        message.id,
        estado,
        origem=message.origem,
        motivo=MOTIVO_COMPROVANTE,
        transport=motorista or message.transport,
    )
    _log(log, f"pedido {message.id} ({message.origem}) passou para {estado} pelo comprovante")
    return True


def _abrir(registry, corpo: object) -> tuple[str, str, str]:
    """Qual dos motoristas registrados abre este recibo, e o que ele diz."""
    for driver in registry.drivers():
        abrir = getattr(driver, "abrir_comprovante", None)
        if abrir is None:
            continue
        try:
            referencia = str(abrir(corpo) or "")
        except Exception:  # o motorista nao pode derrubar a porta do celular
            continue
        if not referencia:
            continue
        try:
            estado = str(driver.comprovante_de(referencia) or "")
        except Exception:  # pragma: no cover - motorista fora do contrato
            estado = ""
        return referencia, estado, str(getattr(driver, "name", "") or "")
    return "", "", ""


def _procurar(store, referencia: str):
    """O recibo traz so o identificador; a origem vem da fila, nunca do celular."""
    for origem in ORIGENS:
        message = store.get(origem, referencia)
        if message is not None:
            return message
    return None


def _log(log, message: str) -> None:
    if log is None:
        return
    try:
        log(message)
    except Exception:
        pass
