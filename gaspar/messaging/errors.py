"""Erros do contrato de mensageria.

Os nomes sao genericos de proposito: quem chama a API local recebe um codigo,
nunca um numero de cliente nem o texto de um SMS.
"""

from __future__ import annotations


class MessagingError(Exception):
    """Base de todo erro desta camada."""


class InvalidRequest(MessagingError):
    """Pedido fora do formato: falta campo, campo invalido ou corpo grande."""


class OriginMismatch(MessagingError):
    """A credencial nao pertence a origem declarada no pedido."""


class UnknownMessage(MessagingError):
    """Nao ha pedido com aquele identificador para aquela origem."""


class QueueFull(MessagingError):
    """A fila guardada atingiu o limite configurado."""


class RateLimited(MessagingError):
    """O limite diario daquela origem foi atingido."""


class CredentialError(MessagingError):
    """Credencial ausente, invalida ou ja existente."""


class StorageError(MessagingError):
    """A fila SQLite nao pode ser aberta ou gravada."""
