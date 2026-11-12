"""Modelos transacionais: o PDV informa o codigo e as variaveis, nunca texto livre."""

from __future__ import annotations

import re

TEMPLATE_VENDA = "venda_confirmada"

_TEMPLATES = {
    TEMPLATE_VENDA: "Venda {venda} concluida{valor}. Obrigado pela preferencia.",
}

_VENDA = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_VALOR = re.compile(r"^\d{1,9}([.,]\d{1,2})?$")


def render_template(template_id: object, variables: object = None) -> str:
    template = _TEMPLATES.get(str(template_id or "").strip())
    if template is None:
        raise ValueError("modelo de mensagem desconhecido")
    dados = variables if variables is not None else {}
    if not isinstance(dados, dict):
        raise ValueError("variaveis do modelo invalidas")
    extras = set(dados) - {"venda", "total"}
    if extras:
        raise ValueError("variavel nao prevista no modelo")
    venda = str(dados.get("venda") or "").strip()
    if not _VENDA.fullmatch(venda):
        raise ValueError("codigo da venda invalido")
    total = str(dados.get("total") or "").strip()
    if total and not _VALOR.fullmatch(total):
        raise ValueError("valor da venda invalido")
    valor = f" no valor de R$ {total}" if total else ""
    return template.format(venda=venda, valor=valor)
