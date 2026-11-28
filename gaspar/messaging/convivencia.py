"""Quem fala com o celular quando os dois motores estao na mesma casa.

O canal do celular pareado pelo Wi-Fi e um so: a porta TCP 49998, que o aplicativo
Android escuta e o computador procura. A ponte de SMS da 1.7 ja usa esse canal, e o
motor 2.0 passou a usa-lo pelo motorista ``android_lan``. Dois programas disputando
o mesmo aparelho e a receita de uma fila que ninguem sabe o que mandou.

A regra, gravada pelo dono do produto em 21/11/2026:

* motor 2.0 ligado (``messaging.enabled`` verdadeiro) com alguma origem escolhendo
  ``android_lan``: o celular e do 2.0, e a ponte 1.7 cede a vez sem tocar na 49998;
* motor 2.0 desligado (o padrao de fabrica): a 1.7 opera exatamente como hoje,
  porque nada desta barra se mexe.

Quem cede nao volta sozinho: a 1.7 retoma o celular quando o Gaspar abre de novo com
o motor 2.0 desligado, ou quando o operador religa a ponte depois de o motor ter saido
de cima do aparelho. Essa consulta e so de configuracao - nenhum dos dois lados abre
conexao para descobrir de quem e o celular.
"""

from __future__ import annotations

from .model import ORIGENS
from .transports.android_lan import NOME_MOTORISTA as NOME_MEIO_CELULAR

__all__ = [
    "NOME_MEIO_CELULAR",
    "celular_reservado",
    "motivo_celular_reservado",
    "origens_com_celular",
]


def origens_com_celular(config: object) -> tuple[str, ...]:
    """Origens cuja escolha de meio e o celular pela rede local."""
    escolhas = getattr(config, "transports", None) or {}
    if not isinstance(escolhas, dict):
        return ()
    return tuple(
        origem
        for origem in ORIGENS
        if str(escolhas.get(origem) or "").strip() == NOME_MEIO_CELULAR
    )


def motor_ligado(config: object) -> bool:
    return bool(getattr(config, "enabled", False))


def celular_reservado(config: object) -> bool:
    """True quando o motor 2.0 esta ligado e vai usar o celular pareado pelo Wi-Fi."""
    if config is None or not motor_ligado(config):
        return False
    return bool(origens_com_celular(config))


def motivo_celular_reservado(config: object) -> str:
    """A frase para o painel e para o log. Vazio quando a 1.7 pode usar o celular."""
    if not celular_reservado(config):
        return ""
    origens = ", ".join(origens_com_celular(config))
    return (
        f"Motor 2.0 ativo com o celular pelo Wi-Fi (origem {origens}): "
        "a ponte 1.7 cede a porta 49998."
    )
