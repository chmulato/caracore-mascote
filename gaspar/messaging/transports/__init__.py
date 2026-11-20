"""Motoristas de envio disponiveis e escolha por origem.

Cada origem (PDV ou Hub) aponta para um motorista na configuracao. Um motorista
pode atender as duas origens ao mesmo tempo - por exemplo, o mesmo modem USB -
mas as filas, as cotas e as credenciais continuam separadas.
"""

from __future__ import annotations

from gaspar.messaging.model import ORIGENS, validar_origem
from gaspar.messaging.transport import Health, SmsTransportDriver

from ..errors import MessagingError


class UnknownTransport(MessagingError):
    """A configuracao apontou para um motorista que nao foi registrado."""


class TransportRegistry:
    """Registro vivo dos motoristas e do que cada origem esta usando."""

    def __init__(self) -> None:
        self._drivers: dict[str, SmsTransportDriver] = {}
        self._by_origin: dict[str, str] = {}

    def register(self, driver: SmsTransportDriver) -> None:
        name = str(getattr(driver, "name", "") or "").strip()
        if not name:
            raise MessagingError("motorista sem nome")
        self._drivers[name] = driver

    def bind(self, origem: str, transport: str) -> None:
        """Liga uma origem a um motorista. Vacuo desliga a origem."""
        origin = validar_origem(origem)
        name = str(transport or "").strip()
        if not name:
            self._by_origin.pop(origin, None)
            return
        if name not in self._drivers:
            raise UnknownTransport(f"motorista desconhecido: {name}")
        self._by_origin[origin] = name

    def unbind(self, origem: str) -> None:
        self._by_origin.pop(validar_origem(origem), None)

    def driver_for(self, origem: str) -> SmsTransportDriver | None:
        name = self._by_origin.get(validar_origem(origem))
        if not name:
            return None
        return self._drivers.get(name)

    def names(self) -> list[str]:
        return sorted(self._drivers)

    def drivers(self) -> list[SmsTransportDriver]:
        """Todos os motoristas registrados, em ordem de nome."""
        return [self._drivers[name] for name in sorted(self._drivers)]

    def bindings(self) -> dict[str, str]:
        return {origem: self._by_origin[origem] for origem in ORIGENS if origem in self._by_origin}

    def health(self) -> dict[str, Health]:
        """Checagem de cada origem ligada, uma vez por motorista repetido."""

        result: dict[str, Health] = {}
        cache: dict[str, Health] = {}
        for origem in ORIGENS:
            driver = self.driver_for(origem)
            if driver is None:
                result[origem] = Health(False, "nenhum meio ativo para esta origem")
                continue
            cached = cache.get(driver.name)
            if cached is None:
                try:
                    cached = driver.health()
                except Exception as exc:  # o motorista nao pode derrubar a checagem
                    cached = Health(False, "falha ao checar o meio", str(exc)[:200])
                cache[driver.name] = cached
            result[origem] = cached
        return result

    def describe(self) -> dict[str, dict]:
        return {name: driver.describe() for name, driver in sorted(self._drivers.items())}

    def shutdown(self) -> None:
        for driver in self._drivers.values():
            try:
                driver.shutdown()
            except Exception:
                pass
