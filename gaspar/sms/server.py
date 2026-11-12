"""Servidor HTTP local para o PDV e para o diagnostico do celular."""

from __future__ import annotations

import base64
import ipaddress
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import signing
from .bridge import BridgeError, InvalidMessage, QueueFull, RateLimited
from .crypto import decrypt, key_from_base64


def is_loopback_address(address: object) -> bool:
    try:
        ip = ipaddress.ip_address(str(address or "").strip())
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_loopback


class SmsHttpServer:
    def __init__(self, bridge, config, host: str = "0.0.0.0", port: int | None = None, on_diagnostic=None, on_log=None):
        self.bridge = bridge
        self.config = config
        self.on_diagnostic = on_diagnostic
        self.on_log = on_log
        self.nonces = signing.NonceCache(config.nonce_ttl_seconds)
        bind_port = config.http_port if port is None else port
        self._httpd = ThreadingHTTPServer((host, bind_port), _Handler)
        self._httpd.app = self
        self._httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    def allows_send_from(self, address: object) -> bool:
        return is_loopback_address(address)

    def request_key(self) -> bytes:
        return (self.config.api_token or "").encode("utf-8")

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

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > 65536:
            return None
        try:
            return self.rfile.read(length)
        except OSError:
            return None

    @staticmethod
    def _parse_json(raw: bytes) -> dict | None:
        try:
            data = json.loads(raw.decode("utf-8"))
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

    def _signature_error(self, raw: bytes, path: str) -> str | None:
        if not self.app.config.require_signed_requests:
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
        if abs(time.time() - timestamp) > self.app.config.request_clock_skew_seconds:
            return "assinatura expirada"
        if not signing.MIN_NONCE_LENGTH <= len(nonce) <= signing.MAX_NONCE_LENGTH:
            return "assinatura invalida"
        if not signing.verify_signature(
            self.app.request_key(), self.command, path, raw, timestamp, nonce, signature
        ):
            return "assinatura invalida"
        if not self.app.nonces.accept(nonce):
            return "pedido repetido"
        return None

    def _send_blocked_here(self) -> bool:
        if self.app.allows_send_from(self.client_address[0]):
            return False
        self._send(403, {"ok": False, "error": "o envio de SMS so e aceito do proprio computador"})
        return True

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
        if path == "/api/sms" or path.startswith("/api/sms/"):
            if self._send_blocked_here():
                return
        if not self._authorized():
            self._send(401, {"ok": False, "error": "token invalido"})
            return
        if path == "/api/sms":
            items = [job.to_public_dict() for job in self.app.bridge.store.recent(20)]
            self._send(200, {"ok": True, "items": items})
            return
        if path == "/api/sms/e2e":
            self._send(
                200,
                {
                    "ok": True,
                    "e2e_required": bool(self.app.config.e2e_required),
                    "phone_key": self.app.config.has_phone_key(),
                    "fingerprint": self.app.config.phone_key_fingerprint(),
                },
            )
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
            if self._send_blocked_here():
                return
            raw = self._read_body()
            if raw is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            if not self._authorized():
                self._send(401, {"ok": False, "error": "token invalido"})
                return
            problem = self._signature_error(raw, path)
            if problem is not None:
                self._send(401, {"ok": False, "error": problem})
                return
            body = self._parse_json(raw)
            if body is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            try:
                job = self.app.bridge.enqueue(
                    body.get("number"),
                    body.get("message"),
                    body.get("venda_id", ""),
                    template=body.get("template", ""),
                    variables=body.get("variaveis", body.get("variables")),
                )
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
                        "sealed": job.sealed,
                        "destino": job.recipient_tag,
                        "conteudo": job.content_tag,
                    },
                )
            return

        if path == "/api/mobile/receipt":
            raw = self._read_body()
            body = self._parse_json(raw) if raw is not None else None
            if body is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            blob = body.get("blob")
            if not isinstance(blob, str) or not blob.strip():
                self._send(400, {"ok": False, "error": "recibo ausente"})
                return
            try:
                raw = base64.b64decode(blob.strip(), validate=True)
                receipt = json.loads(
                    decrypt(key_from_base64(self.app.config.shared_secret_b64), raw).decode("utf-8")
                )
            except Exception:
                self._send(400, {"ok": False, "error": "recibo invalido"})
                return
            if not isinstance(receipt, dict):
                self._send(400, {"ok": False, "error": "recibo invalido"})
                return
            job_id = str(receipt.get("id") or "").strip()
            event = str(receipt.get("status") or "").strip()
            detail = str(receipt.get("detail") or "")
            if not job_id or event not in ("sent", "delivered", "failed"):
                self._send(400, {"ok": False, "error": "recibo invalido"})
                return
            job = self.app.bridge.apply_receipt(job_id, event, detail)
            if job is None:
                self._send(404, {"ok": False, "error": "pedido nao encontrado"})
            else:
                self._send(202, {"ok": True, "status": job.status})
            return

        if path == "/api/mobile/key":
            raw = self._read_body()
            body = self._parse_json(raw) if raw is not None else None
            if body is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            blob = body.get("blob")
            if not isinstance(blob, str) or not blob.strip():
                self._send(400, {"ok": False, "error": "pedido ausente"})
                return
            try:
                clear = decrypt(
                    key_from_base64(self.app.config.shared_secret_b64),
                    base64.b64decode(blob.strip(), validate=True),
                )
                pedido = json.loads(clear.decode("utf-8"))
            except Exception:
                self._send(400, {"ok": False, "error": "pedido invalido"})
                return
            if not isinstance(pedido, dict):
                self._send(400, {"ok": False, "error": "pedido invalido"})
                return
            config = self.app.config
            if not config.set_phone_public_key(pedido.get("phone_public_key")):
                self._send(
                    409,
                    {"ok": False, "error": "chave do celular ja registrada; pareie o celular de novo"},
                )
                return
            config.save()
            self.app.log(f"Chave de criptografia do celular registrada ({config.phone_key_fingerprint()}).")
            self._send(200, {"ok": True, "fingerprint": config.phone_key_fingerprint()})
            return

        if path == "/api/mobile/diagnostic":
            raw = self._read_body()
            body = self._parse_json(raw) if raw is not None else None
            if body is None:
                self._send(400, {"ok": False, "error": "corpo invalido"})
                return
            if not self.app.config.setup_token_valid(body.get("token")):
                self._send(403, {"ok": False, "error": "token de pareamento invalido ou expirado"})
                return
            config = self.app.config
            phone_key = str(body.get("phone_public_key") or "").strip()
            if phone_key:
                if not config.set_phone_public_key(phone_key, allow_replace=True):
                    self._send(400, {"ok": False, "error": "chave do celular invalida"})
                    return
            elif config.e2e_required:
                self._send(
                    400,
                    {
                        "ok": False,
                        "error": "aplicativo do celular desatualizado; atualize para a versao com criptografia",
                    },
                )
                return
            config.last_diagnostic_at = time.time()
            config.last_diagnostic_sms_ok = bool(body.get("sms_ok"))
            config.last_diagnostic_battery_ok = bool(body.get("battery_ok"))
            config.last_diagnostic_message = str(body.get("message") or "")[:500]
            config.setup_token = ""
            config.save()
            if config.has_phone_key():
                self.app.log(
                    f"Diagnostico do celular recebido; pareamento concluido com chave {config.phone_key_fingerprint()}."
                )
            else:
                self.app.log("Diagnostico do celular recebido; pareamento concluido.")
            if self.app.on_diagnostic is not None:
                try:
                    self.app.on_diagnostic(body)
                except Exception:
                    pass
            self._send(200, {"ok": True, "paired": True})
            return

        self._send(404, {"ok": False, "error": "rota desconhecida"})
