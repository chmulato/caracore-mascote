"""Descoberta do endereco do computador na rede local."""

from __future__ import annotations

import socket


def lan_ip() -> str:
    """Endereco IPv4 usado para sair para a rede; nao envia pacotes."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
            if address and not address.startswith("127."):
                return address
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return ""
