"""Servidor HTTP local para o PDV e para o diagnostico do celular."""

from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .bridge import BridgeError, InvalidMessage, QueueFull, RateLimited


class SmsHttpServer:
    def __init__(self, bridge, config, host: str = "0.0.0.0", port: int | None = None, on_diagnostic=None, on_log=None):
        self.bridge = bridge
        self.config = config
        self.on_diagnostic = on_diagnostic
        self.on_log = on_log
        bind_port = config.http_port if port is None else port
        self._httpd = ThreadingHTTPServer((host, bind_port), _Handler)
        self._httpd.app = self
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
            name="gaspar-sms-http",
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

    def log(self, message: str) -> None:
        if self.on_log is not None:
            try:
                self.on_log(message)
            except Exception:
                pass


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GasparSMS/1.0"

    def log_message(self, fmt, *args) -> None:
        return

    @property
    def app(self) -> SmsHttpServer:
        return self.server.app

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass
        self.close_connection = True

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > 65536:
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _authorized(self) -> bool:
        expected = self.app.config.api_token
        provided = (self.headers.get("X-Api-Token") or "").strip()
        if not provided:
            header = (self.headers.get("Authorization") or "").strip()
            if header.lower().startswith("bearer "):
                provided = header[7:].strip()
        return bool(expected) and bool(provided) and secrets.compare_digest(provided, expected)

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/health":
            stats = self.app.bridge.stats()
            counts = stats["counts"]
            self._send(
                200,
                {
                    "ok": True,
                    "phone_online": stats["phone"]["online"],
                    "pending": counts.get("fila", 0) + counts.get("enviando", 0),
                },
            )
            return
        if not self._authorized():
            self._send(401, {"ok": False, "error": "token invalido"})
            return
        if path == "/api/sms":
            items = [job.to_dict() for job in self.app.bridge.store.recent(20)]
            self._send(200, {"ok": True, "items": items})
            return
        if path.startswith("/api/sms/"):
            job = self.app.bridge.store.get(path.rsplit("/", 1)[-1])
            if job is None:
                self._send(404, {"ok": False, "error": "pedido nao encontrado"})
            else:
                self._send(200, {"ok": True, "job": job.to_dict()})
            return
        self._send(404, {"ok": False, "error": "rota desconhecida"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/sms":
            if not self._authorized():
                self._send(401, {"ok": False, "error": "token invalido"})
                return
            body = self._read_json()
            if body is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            try:
                job = self.app.bridge.enqueue(body.get("number"), body.get("message"), body.get("venda_id", ""))
            except InvalidMessage as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            except RateLimited as exc:
                self._send(429, {"ok": False, "error": str(exc)})
            except QueueFull as exc:
                self._send(507, {"ok": False, "error": str(exc)})
            except BridgeError as exc:
                self._send(400, {"ok": False, "error": str(exc)})
            else:
                self._send(
                    202,
                    {
                        "ok": True,
                        "id": job.id,
                        "status": job.status,
                        "confirmed": job.confirmed,
                    },
                )
            return

        if path == "/api/mobile/diagnostic":
            body = self._read_json()
            if body is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            if not self.app.config.setup_token_valid(body.get("token")):
                self._send(403, {"ok": False, "error": "token de pareamento invalido ou expirado"})
                return
            config = self.app.config
            config.last_diagnostic_at = time.time()
            config.last_diagnostic_sms_ok = bool(body.get("sms_ok"))
            config.last_diagnostic_battery_ok = bool(body.get("battery_ok"))
            config.last_diagnostic_message = str(body.get("message") or "")[:500]
            config.setup_token = ""
            config.save()
            self.app.log("Diagnostico do celular recebido; pareamento concluido.")
            if self.app.on_diagnostic is not None:
                try:
                    self.app.on_diagnostic(body)
                except Exception:
                    pass
            self._send(200, {"ok": True, "paired": True})
            return

        self._send(404, {"ok": False, "error": "rota desconhecida"})
