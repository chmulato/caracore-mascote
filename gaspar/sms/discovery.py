"""Procura o celular na mesma rede Wi-Fi."""

from __future__ import annotations

import socket
import time

from .protocol import DISCOVER_MAGIC, DISCOVERY_PORT, parse_discovery


def _broadcast_addresses() -> set[str]:
    targets = {"255.255.255.255"}
    try:
        import psutil

        for addresses in psutil.net_if_addrs().values():
            for address in addresses:
                if address.family == socket.AF_INET and address.broadcast:
                    targets.add(address.broadcast)
    except Exception:
        pass
    return targets


def discover(timeout: float = 1.6, port: int = DISCOVERY_PORT) -> list[tuple[str, int]]:
    """Envia o aviso de descoberta e devolve os celulares que responderam."""
    targets = _broadcast_addresses()
    found: dict[str, tuple[str, int]] = {}
    deadline = time.monotonic() + max(0.4, timeout)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 0))
        sock.settimeout(0.2)
        next_send = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_send:
                for address in targets:
                    try:
                        sock.sendto(DISCOVER_MAGIC, (address, port))
                    except OSError:
                        pass
                next_send = now + 0.4
            try:
                data, _ = sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            parsed = parse_discovery(data)
            if parsed:
                found[parsed[0]] = parsed
    return list(found.values())
