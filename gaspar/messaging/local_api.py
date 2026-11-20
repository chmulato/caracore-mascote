"""Contrato local da barra de mensagens: HTTP em 127.0.0.1, sem bibliotecas do Gaspar.

O pedido minimo do PDV ou do Hub e::

    {"id_externo": "venda-123", "destino": "11999998888", "mensagem": "Oi!"}

Quem esta pedindo vem da credencial (``X-Api-Token``), nunca do corpo. Se o corpo
ainda mandar ``origem`` e ela nao bater com a credencial, o pedido e recusado com
403 e nada entra na fila.

O ``202`` significa uma coisa e so uma: o pedido ficou guardado com seguranca.
Ele nao diz que o SMS chegou - para isso existe a trilha de notificacoes
(``GET /v2/events``).
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from gaspar.sms import signing

from .config import MAX_BODY_BYTES, MessagingConfig, is_loopback_host
from .errors import InvalidRequest, MessagingError, QueueFull, StorageError, UnknownMessage
from .model import STATUS_ENTREGUE, STATUS_FALHOU, STATUS_INCERTO, validar_origem

SERVICE_NAME = "gaspar-messaging"
TOKEN_HEADER = "X-Api-Token"
MAX_REASON = 200
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
_MESSAGES_PREFIX = "/v2/messages/"
_REPLIES_PREFIX = "/v2/replies/"
_CONFIRM_SUFFIX = "/confirm"
_ASSIGN_SUFFIX = "/assign"


class MessagingApi:
    """Servidor HTTP do contrato local. Nasce parado e so abre com a barra ligada."""

    def __init__(self, service, *, host: str | None = None, port: int | None = None):
        config: MessagingConfig = service.config
        self.service = service
        self.config = config
        self.nonces = signing.NonceCache(config.nonce_ttl_seconds)
        bind_host = config.host if host is None else str(host)
        bind_port = int(config.port if port is None else port)
        self._httpd = ThreadingHTTPServer((bind_host, bind_port), _ApiHandler)
        self._httpd.api = self
        self._httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="gaspar-messaging-http",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        try:
            self._httpd.shutdown()
        except Exception:
            pass
        try:
            self._httpd.server_close()
        finally:
            self._thread = None

    def origin_for(self, token: object) -> str | None:
        """A origem e o que a credencial representa. None quando ela nao vale nada."""
        return self.service.credentials.resolve(token)

    def signing_key(self, origem: str) -> bytes:
        return self.service.credentials.secret_for(origem).encode("utf-8")

    def allows_local_only(self, address: object) -> bool:
        return is_loopback_host(address)


class _ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GasparMessaging/2.0"

    #: preenchido por ``_authenticate`` antes de qualquer rota usar
    _origem: str = ""

    def log_message(self, fmt, *args) -> None:
        return

    @property
    def api(self) -> MessagingApi:
        return self.server.api

    # ---------------------------------------------------------------- sair

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass
        self.close_connection = True

    def _fail(self, code: int, error: object, **extra) -> None:
        self._send(code, {"ok": False, "error": str(error)[:MAX_REASON], **extra})

    # -------------------------------------------------------------- entrada

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            return None
        try:
            return self.rfile.read(length)
        except OSError:
            return None

    @staticmethod
    def _parse_json(raw: bytes) -> dict | None:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _token(self) -> str:
        provided = (self.headers.get(TOKEN_HEADER) or "").strip()
        if provided:
            return provided
        header = (self.headers.get("Authorization") or "").strip()
        if header.lower().startswith("bearer "):
            return header[7:].strip()
        return ""

    def _signature_problem(self, raw: bytes, path: str, origem: str) -> str | None:
        if not self.api.config.require_signed_requests:
            return None
        timestamp_raw = (self.headers.get(signing.TIMESTAMP_HEADER) or "").strip()
        nonce = (self.headers.get(signing.NONCE_HEADER) or "").strip()
        signature = (self.headers.get(signing.SIGNATURE_HEADER) or "").strip()
        if not timestamp_raw or not nonce or not signature:
            return "assinatura ausente"
        try:
            timestamp = int(timestamp_raw)
        except ValueError:
            return "assinatura invalida"
        if abs(time.time() - timestamp) > self.api.config.request_clock_skew_seconds:
            return "assinatura expirada"
        if not signing.MIN_NONCE_LENGTH <= len(nonce) <= signing.MAX_NONCE_LENGTH:
            return "assinatura invalida"
        key = self.api.signing_key(origem)
        if not key:
            return "a credencial desta origem nao tem segredo de assinatura"
        if not signing.verify_signature(key, self.command, path, raw, timestamp, nonce, signature):
            return "assinatura invalida"
        if not self.api.nonces.accept(nonce):
            return "pedido repetido"
        return None

    # ------------------------------------------------------------ autenticar

    def _authenticate(self, *, mutating: bool, path: str = "", raw: bytes = b"") -> str | None:
        """Devolve a origem da credencial, ou None depois de ja ter respondido o erro."""
        client = self.client_address[0] if self.client_address else ""
        if not self.api.allows_local_only(client):
            self._fail(403, "o contrato local so aceita pedidos do proprio computador")
            return None
        origem = self.api.origin_for(self._token())
        if origem is None:
            self._fail(401, "credencial invalida ou ausente")
            return None
        self._origem = origem
        if mutating:
            problem = self._signature_problem(raw, path, origem)
            if problem is not None:
                self._fail(401, problem)
                return None
        return origem

    # ---------------------------------------------------------------- GET

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path == "/v2/health":
            self._health()
            return
        if path in ("/", "/v2"):
            self._send(200, {"ok": True, "servico": SERVICE_NAME, "fase": "alpha"})
            return
        if path == "/v2/messages":
            if self._authenticate(mutating=False) is None:
                return
            self._by_external(query)
            return
        if path == "/v2/events":
            if self._authenticate(mutating=False) is None:
                return
            self._events(query)
            return
        if path == "/v2/replies":
            if self._authenticate(mutating=False) is None:
                return
            self._replies(query)
            return
        if path.startswith(_MESSAGES_PREFIX):
            if self._authenticate(mutating=False) is None:
                return
            self._one_message(path[len(_MESSAGES_PREFIX) :])
            return
        self._fail(404, "rota desconhecida")

    def _health(self) -> None:
        service = self.api.service
        meios = {}
        for origem, health in service.registry.health().items():
            driver = service.registry.driver_for(origem)
            meios[origem] = {"meio": driver.name if driver else "", **health.to_dict()}
        self._send(
            200,
            {
                "ok": True,
                "servico": SERVICE_NAME,
                "fase": "alpha",
                "ativo": bool(self.api.config.enabled),
                "porta": self.api.port,
                "meios": meios,
                "respostas_por_identificar": service.store.stats()["respostas_por_identificar"],
            },
        )

    def _one_message(self, message_id: str) -> None:
        message = self.api.service.store.get(self._origem, message_id.strip("/"))
        if message is None:
            self._fail(404, "pedido nao encontrado")
            return
        self._send(200, {"ok": True, "pedido": message.to_public_dict()})

    def _by_external(self, query: dict) -> None:
        external = str((query.get("id_externo") or [""])[0])
        if not external.strip():
            self._fail(400, "informe id_externo")
            return
        try:
            message = self.api.service.store.get_by_external(self._origem, external)
        except InvalidRequest as exc:
            self._fail(400, str(exc))
            return
        if message is None:
            self._fail(404, "pedido nao encontrado")
            return
        self._send(200, {"ok": True, "pedido": message.to_public_dict()})

    def _events(self, query: dict) -> None:
        cursor = _as_int((query.get("from") or ["0"])[0], 0, low=0)
        limit = _as_int((query.get("limit") or [str(DEFAULT_LIMIT)])[0], DEFAULT_LIMIT, low=1)
        events = self.api.service.store.events_since(self._origem, cursor, limit)
        self._send(
            200,
            {
                "ok": True,
                "eventos": [event.to_dict() for event in events],
                "cursor": events[-1].seq if events else cursor,
            },
        )

    def _replies(self, query: dict) -> None:
        limit = _as_int((query.get("limit") or [str(DEFAULT_LIMIT)])[0], DEFAULT_LIMIT, low=1)
        payload = []
        for inbound in self.api.service.store.inbound_for(self._origem, limit):
            data = inbound.to_public_dict()
            data["mensagem"] = inbound.text
            payload.append(data)
        self._send(200, {"ok": True, "respostas": payload})

    # --------------------------------------------------------------- POST

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        kind = _post_route(path)
        if kind is None:
            self._fail(404, "rota desconhecida")
            return
        raw = self._read_body()
        if raw is None:
            self._fail(400, "corpo invalido")
            return
        if self._authenticate(mutating=True, path=path, raw=raw) is None:
            return
        body = self._parse_json(raw)
        if body is None:
            self._fail(400, "corpo invalido")
            return
        if kind == "mensagem":
            self._enqueue(body)
        elif kind == "confirmar":
            self._confirm(path[len(_MESSAGES_PREFIX) : -len(_CONFIRM_SUFFIX)].strip("/"), body)
        else:
            self._assign(path[len(_REPLIES_PREFIX) : -len(_ASSIGN_SUFFIX)].strip("/"), body)

    def _enqueue(self, body: dict) -> None:
        service = self.api.service
        claimed = str(body.get("origem") or "").strip()
        if claimed and not _same_origin(claimed, self._origem):
            self._fail(403, "a credencial nao pertence a origem informada", codigo="origem_diferente")
            return
        if service.store.day_count(self._origem) >= service.config.daily_limit_per_origin:
            self._fail(429, "cota diaria desta origem esgotada")
            return
        try:
            message, created = service.store.enqueue(
                origem=self._origem,
                external_id=str(body.get("id_externo") or ""),
                recipient=str(body.get("destino") or ""),
                text=str(body.get("mensagem") or ""),
                idempotency_key=str(body.get("chave_repeticao") or ""),
            )
        except InvalidRequest as exc:
            self._fail(400, str(exc))
        except QueueFull as exc:
            self._fail(507, str(exc))
        except StorageError as exc:
            self._fail(500, str(exc))
        except MessagingError as exc:  # pragma: no cover - defesa do contrato
            self._fail(400, str(exc))
        else:
            self._send(
                202,
                {
                    "ok": True,
                    "criado": created,
                    "pedido": message.to_public_dict(),
                    "aviso": "o pedido esta guardado; a entrega se acompanha por /v2/events",
                },
            )

    def _confirm(self, message_id: str, body: dict) -> None:
        service = self.api.service
        message = service.store.get(self._origem, message_id)
        if message is None:
            self._fail(404, "pedido nao encontrado")
            return
        if message.status != STATUS_INCERTO:
            self._fail(409, "so um envio em duvida pode ser conferido assim")
            return
        mapping = {"entregue": STATUS_ENTREGUE, "falhou": STATUS_FALHOU}
        wanted = mapping.get(str(body.get("status") or "").strip().lower())
        if wanted is None:
            self._fail(400, "use entregue ou falhou")
            return
        try:
            updated = service.store.resolve_uncertain(
                message_id,
                wanted,
                motivo=str(body.get("motivo") or "conferido pelo produto"),
            )
        except (InvalidRequest, UnknownMessage) as exc:
            self._fail(409, str(exc))
        except StorageError as exc:  # pragma: no cover - disco cheio
            self._fail(500, str(exc))
        else:
            self._send(200, {"ok": True, "pedido": updated.to_public_dict()})

    def _assign(self, inbound_id: str, body: dict) -> None:
        """O produto assume uma resposta que ainda nao tem dono, provendo o id_externo."""
        service = self.api.service
        try:
            message = service.store.get_by_external(self._origem, str(body.get("id_externo") or ""))
        except InvalidRequest as exc:
            self._fail(400, str(exc))
            return
        if message is None:
            self._fail(404, "nenhum pedido desta origem com esse id_externo")
            return
        current = service.store.get_inbound(inbound_id)
        if current is None:
            self._fail(404, "resposta nao encontrada")
            return
        if current.roteada:
            self._fail(409, "esta resposta ja tem dono")
            return
        try:
            routed = service.store.route_inbound(
                inbound_id, self._origem, message.id, motivo="atribuida pelo produto"
            )
        except UnknownMessage as exc:
            self._fail(404, str(exc))
        except StorageError as exc:  # pragma: no cover - disco cheio
            self._fail(500, str(exc))
        else:
            self._send(200, {"ok": True, "resposta": routed.to_public_dict() if routed else None})


def _post_route(path: str) -> str | None:
    if path == "/v2/messages":
        return "mensagem"
    if path.startswith(_MESSAGES_PREFIX) and path.endswith(_CONFIRM_SUFFIX):
        return "confirmar"
    if path.startswith(_REPLIES_PREFIX) and path.endswith(_ASSIGN_SUFFIX):
        return "assign"
    return None


def _as_int(value: object, default: int, *, low: int, high: int = MAX_LIMIT) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        number = int(default)
    return min(max(number, low), high)


def _same_origin(claimed: str, real: str) -> bool:
    try:
        return validar_origem(claimed) == real
    except ValueError:
        return False
