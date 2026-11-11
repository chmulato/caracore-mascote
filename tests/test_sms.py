"""Testes da ponte local de SMS (sem rede externa e sem dados reais)."""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from gaspar.sms.bridge import (
    InvalidMessage,
    RateLimited,
    SmsBridge,
    normalize_message,
    normalize_number,
)
from gaspar.sms.client import PhoneOffline, SendResult
from gaspar.sms.config import load_config
from gaspar.sms.crypto import decrypt, encrypt, key_from_base64
from gaspar.sms.protocol import build_command, frame, parse_discovery
from gaspar.sms.server import SmsHttpServer
from gaspar.sms.store import (
    SmsJob,
    SmsStore,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_SENT,
    mask_number,
)


def make_config(tmp: str):
    config = load_config(Path(tmp) / "sms.json")
    config.phone_host = "127.0.0.1"
    config.phone_port = 49998
    config.save()
    return config


def make_store(tmp: str, max_jobs: int = 50) -> SmsStore:
    return SmsStore(Path(tmp) / "sms_state.json", Path(tmp) / "sms_log.jsonl", max_jobs=max_jobs)


class FakeClient:
    def __init__(self, outcomes, calls):
        self._outcomes = list(outcomes)
        self._calls = calls

    def send(self, number, message, msg_id="", timestamp=None, base_url=""):
        self._calls.append((number, message, msg_id))
        outcome = self._outcomes.pop(0) if self._outcomes else SendResult(acknowledged=False)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def factory(outcomes, calls):
    client = FakeClient(outcomes, calls)
    return lambda host, port, key: client


def wait_for(store: SmsStore, job_id: str, statuses: set[str], timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = store.get(job_id)
        if job is not None and job.status in statuses:
            return job
        time.sleep(0.02)
    return store.get(job_id)


class ConfigTests(unittest.TestCase):
    def test_generates_secrets_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(Path(tmp) / "sms.json")
            self.assertTrue(config.shared_secret_b64)
            self.assertTrue(config.api_token)
            payload = config.setup_payload("192.168.0.10")
            parts = payload.split("|")
            self.assertEqual(len(parts), 6)
            self.assertEqual(parts[0], "CARACORE-SETUP")
            self.assertEqual(parts[1], "192.168.0.10")
            self.assertEqual(int(parts[2]), config.http_port)
            self.assertEqual(parts[3], config.shared_secret_b64)
            self.assertTrue(config.setup_token_valid(parts[4]))
            reloaded = load_config(Path(tmp) / "sms.json")
            self.assertEqual(reloaded.api_token, config.api_token)
            self.assertEqual(reloaded.shared_secret_b64, config.shared_secret_b64)

    def test_setup_token_is_single_use_after_invalidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(Path(tmp) / "sms.json")
            token = config.new_setup_token()
            self.assertTrue(config.setup_token_valid(token))
            config.setup_token = ""
            self.assertFalse(config.setup_token_valid(token))

    def test_short_key_is_hashed_like_android(self):
        raw = b"chave-curta"
        secret = base64.b64encode(raw).decode("ascii")
        self.assertEqual(key_from_base64(secret), hashlib.sha256(raw).digest())


class CryptoProtocolTests(unittest.TestCase):
    def test_android_side_decrypts_and_tamper_is_rejected(self):
        key = bytes(range(32))
        blob = encrypt(key, b"oi")
        self.assertEqual(len(blob[:12]), 12)
        plain = AESGCM(key).decrypt(blob[:12], blob[12:], None)
        self.assertEqual(plain, b"oi")
        tampered = bytearray(blob)
        tampered[-1] ^= 1
        with self.assertRaises(Exception):
            decrypt(key, bytes(tampered))

    def test_frame_and_command(self):
        payload = b"abc"
        framed = frame(payload)
        self.assertEqual(framed[:4], (3).to_bytes(4, "big"))
        command = json.loads(build_command("5511999999999", "ola", "id1", 123.5))
        self.assertEqual(command["action"], "send_sms")
        self.assertEqual(command["number"], "5511999999999")
        self.assertEqual(command["message"], "ola")
        self.assertEqual(command["id"], "id1")
        self.assertEqual(command["ts"], 123)

    def test_discovery_parsing(self):
        self.assertEqual(parse_discovery(b"CARACORE-APK|192.168.0.7|49998"), ("192.168.0.7", 49998))
        self.assertIsNone(parse_discovery(b"CARACORE-APK|192.168.0.7|abc"))
        self.assertIsNone(parse_discovery(b"outro|1|2"))

    def test_number_and_message_validation(self):
        self.assertEqual(normalize_number("(11) 99999-9999"), "11999999999")
        self.assertEqual(normalize_number("+55 11 99999-9999"), "+5511999999999")
        with self.assertRaises(InvalidMessage):
            normalize_number("123")
        with self.assertRaises(InvalidMessage):
            normalize_message("   ")
        with self.assertRaises(InvalidMessage):
            normalize_message("x" * 481)


class StoreTests(unittest.TestCase):
    def test_persists_and_reloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(tmp)
            job = SmsJob.create("5511999999999", "mensagem", "venda-1")
            store.add(job)
            store.update(job.id, status=STATUS_SENT, confirmed=True)
            again = make_store(tmp)
            loaded = again.get(job.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.status, STATUS_SENT)
            self.assertTrue(loaded.confirmed)
            self.assertEqual(mask_number("5511999999999"), "*********9999")


class BridgeTests(unittest.TestCase):
    def test_successful_send_with_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            calls = []
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"status": "accepted"})], calls),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola", "venda-1")
                done = wait_for(store, job.id, {STATUS_SENT})
                self.assertEqual(done.status, STATUS_SENT)
                self.assertTrue(done.confirmed)
                self.assertEqual(len(calls), 1)
            finally:
                bridge.stop()

    def test_rejects_when_cell_answers_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            calls = []
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"ok": False, "error": "app inativo"})], calls),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                done = wait_for(store, job.id, {STATUS_FAILED})
                self.assertEqual(done.status, STATUS_FAILED)
                self.assertIn("app inativo", done.error)
            finally:
                bridge.stop()

    def test_receipt_marks_delivered_and_is_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"ok": True})], []),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                wait_for(store, job.id, {STATUS_SENT})
            finally:
                bridge.stop()
            delivered = bridge.apply_receipt(job.id, "delivered", "entregue")
            self.assertEqual(delivered.status, STATUS_DELIVERED)
            self.assertTrue(delivered.confirmed)
            self.assertGreater(delivered.delivered_at, 0)
            bridge.apply_receipt(job.id, "sent", "aceito")
            self.assertEqual(store.get(job.id).status, STATUS_DELIVERED)
            bridge.apply_receipt(job.id, "failed", "falha")
            self.assertEqual(store.get(job.id).status, STATUS_DELIVERED)
            self.assertEqual(store.counts()[STATUS_DELIVERED], 1)

    def test_receipt_failure_after_sent_marks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            job = bridge.enqueue("5511999999999", "ola")
            bridge.apply_receipt(job.id, "sent", "aceito")
            failed = bridge.apply_receipt(job.id, "failed", "sem credito")
            self.assertEqual(failed.status, STATUS_FAILED)
            self.assertIn("sem credito", failed.error)
            self.assertIsNone(bridge.apply_receipt("nao-existe", "delivered"))

    def test_command_carries_gaspar_address(self):
        payload = json.loads(build_command("5511999999999", "oi", "id-1", 10.0, "http://192.168.0.10:8766"))
        self.assertEqual(payload["base"], "http://192.168.0.10:8766")
        self.assertEqual(payload["id"], "id-1")

    def test_retries_when_phone_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            calls = []
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([PhoneOffline("sem rede"), SendResult(False)], calls),
                retry_delay=0.01,
                max_attempts=2,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                done = wait_for(store, job.id, {STATUS_SENT})
                self.assertEqual(done.status, STATUS_SENT)
                self.assertEqual(done.attempts, 2)
                self.assertEqual(len(calls), 2)
            finally:
                bridge.stop()

    def test_marks_failed_after_last_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([PhoneOffline("sem rede")], []),
                retry_delay=0.01,
                max_attempts=1,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                done = wait_for(store, job.id, {STATUS_FAILED})
                self.assertEqual(done.status, STATUS_FAILED)
                self.assertIn("sem rede", done.error)
            finally:
                bridge.stop()

    def test_deduplicates_sale_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            calls = []
            bridge = SmsBridge(config, store, client_factory=factory([], calls))
            bridge.start()
            try:
                first = bridge.enqueue("5511999999999", "ola", "venda-9")
                second = bridge.enqueue("5511999999999", "ola", "venda-9")
                self.assertEqual(first.id, second.id)
            finally:
                bridge.stop()
            self.assertEqual(len(calls), 1)

    def test_rate_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            config.max_per_minute = 1
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            bridge.start()
            try:
                bridge.enqueue("5511999999999", "primeira")
                with self.assertRaises(RateLimited):
                    bridge.enqueue("5511888888888", "segunda")
            finally:
                bridge.stop()

    def test_restores_queued_jobs_on_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            pending = SmsJob.create("5511999999999", "pendente")
            store.add(pending)
            calls = []
            bridge = SmsBridge(config, store, client_factory=factory([], calls))
            bridge.start()
            try:
                done = wait_for(store, pending.id, {STATUS_SENT})
                self.assertEqual(done.status, STATUS_SENT)
            finally:
                bridge.stop()

    def test_interrupted_send_is_not_resent(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            pending = SmsJob.create("5511999999999", "interrompido")
            pending.status = "enviando"
            store.add(pending)
            calls = []
            bridge = SmsBridge(config, store, client_factory=factory([], calls))
            bridge.start()
            try:
                time.sleep(0.2)
                self.assertEqual(store.get(pending.id).status, STATUS_FAILED)
                self.assertEqual(calls, [])
            finally:
                bridge.stop()


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = make_config(self.tmp.name)
        self.config.api_token = "token-de-teste"
        self.config.save()
        self.store = make_store(self.tmp.name)
        self.calls = []
        self.bridge = SmsBridge(
            self.config,
            self.store,
            client_factory=factory([], self.calls),
            retry_delay=0.01,
        )
        self.bridge.start()
        self.server = SmsHttpServer(self.bridge, self.config, host="127.0.0.1", port=0)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.bridge.stop()
        self.tmp.cleanup()

    def request(self, method: str, path: str, body=None, token: str | None = None):
        connection = HTTPConnection("127.0.0.1", self.server.port, timeout=3)
        headers = {}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-Api-Token"] = token
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_health_is_public(self):
        code, data = self.request("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])

    def test_sms_requires_token(self):
        code, data = self.request("POST", "/api/sms", {"number": "5511999999999", "message": "oi"})
        self.assertEqual(code, 401)
        self.assertFalse(data["ok"])

    def test_accepts_and_reports_job(self):
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "5511999999999", "message": "oi", "venda_id": "v1"},
            token="token-de-teste",
        )
        self.assertEqual(code, 202)
        job_id = data["id"]
        done = wait_for(self.store, job_id, {STATUS_SENT})
        self.assertEqual(done.status, STATUS_SENT)
        code, data = self.request("GET", f"/api/sms/{job_id}", token="token-de-teste")
        self.assertEqual(code, 200)
        self.assertEqual(data["job"]["status"], STATUS_SENT)
        code, data = self.request("GET", "/api/sms", token="token-de-teste")
        self.assertEqual(code, 200)
        self.assertEqual(len(data["items"]), 1)

    def test_rejects_invalid_number(self):
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "abc", "message": "oi"},
            token="token-de-teste",
        )
        self.assertEqual(code, 400)
        self.assertFalse(data["ok"])

    def receipt_blob(self, payload: dict) -> str:
        key = key_from_base64(self.config.shared_secret_b64)
        return base64.b64encode(encrypt(key, json.dumps(payload).encode("utf-8"))).decode("ascii")

    def test_receipt_marks_delivered_without_api_token(self):
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "5511999999999", "message": "oi"},
            token="token-de-teste",
        )
        self.assertEqual(code, 202)
        job_id = data["id"]
        wait_for(self.store, job_id, {STATUS_SENT})
        blob = self.receipt_blob({"id": job_id, "status": "delivered", "detail": "entregue"})
        code, data = self.request("POST", "/api/mobile/receipt", {"blob": blob})
        self.assertEqual(code, 202)
        self.assertEqual(data["status"], STATUS_DELIVERED)
        job = self.store.get(job_id)
        self.assertEqual(job.status, STATUS_DELIVERED)
        self.assertTrue(job.confirmed)

    def test_receipt_rejects_tampered_or_unknown(self):
        blob = self.receipt_blob({"id": "x", "status": "delivered"})
        code, _ = self.request("POST", "/api/mobile/receipt", {"blob": blob[:-8] + "AAAAAAAA"})
        self.assertEqual(code, 400)
        blob = self.receipt_blob({"id": "nao-existe", "status": "delivered"})
        code, _ = self.request("POST", "/api/mobile/receipt", {"blob": blob})
        self.assertEqual(code, 404)
        blob = self.receipt_blob({"id": "x", "status": "qualquer"})
        code, _ = self.request("POST", "/api/mobile/receipt", {"blob": blob})
        self.assertEqual(code, 400)

    def test_diagnostic_token_is_single_use(self):
        token = self.config.new_setup_token()
        self.config.save()
        code, data = self.request(
            "POST",
            "/api/mobile/diagnostic",
            {"token": token, "sms_ok": True, "battery_ok": False, "message": ""},
        )
        self.assertEqual(code, 200)
        self.assertTrue(data["paired"])
        code, _ = self.request(
            "POST",
            "/api/mobile/diagnostic",
            {"token": token, "sms_ok": True, "battery_ok": False, "message": ""},
        )
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
