"""Testes da ponte local de SMS (sem rede externa e sem dados reais)."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from gaspar.sms import e2e, signing
from gaspar.sms.audit import AuditLog
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
from gaspar.sms.server import SmsHttpServer, is_loopback_address
from gaspar.sms.store import (
    SmsJob,
    SmsStore,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_SENT,
    mask_number,
)
from gaspar.sms.templates import render_template


def make_config(tmp: str):
    config = load_config(Path(tmp) / "sms.json")
    config.phone_host = "127.0.0.1"
    config.phone_port = 49998
    config.only_templates = False
    private_der, public_raw = e2e.generate_keypair()
    config.set_phone_public_key(base64.b64encode(public_raw).decode("ascii"))
    config.save()
    config.test_private_key = private_der
    return config


def make_store(tmp: str, max_jobs: int = 50) -> SmsStore:
    audit = AuditLog(Path(tmp) / "sms_audit.jsonl")
    return SmsStore(Path(tmp) / "sms_state.json", audit, max_jobs=max_jobs)


def open_job(config, job) -> dict:
    raw = e2e.open_sealed(config.test_private_key, job.envelope, job.id.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


class FakeClient:
    def __init__(self, outcomes, calls):
        self._outcomes = list(outcomes)
        self._calls = calls

    def send(self, envelope="", msg_id="", timestamp=None, base_url="", sequence=0, number="", message=""):
        self._calls.append(
            {"envelope": envelope, "id": msg_id, "sequence": sequence, "number": number, "message": message}
        )
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
        command = json.loads(build_command("envelope-cifrado", "id1", 123.5))
        self.assertEqual(command["action"], "send_sms")
        self.assertEqual(command["envelope"], "envelope-cifrado")
        self.assertNotIn("number", command)
        self.assertNotIn("message", command)
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
        payload = json.loads(
            build_command(
                envelope="envelope",
                msg_id="id-1",
                timestamp=10.0,
                base_url="http://192.168.0.10:8766",
                sequence=7,
            )
        )
        self.assertEqual(payload["base"], "http://192.168.0.10:8766")
        self.assertEqual(payload["id"], "id-1")
        self.assertEqual(payload["seq"], 7)

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


class TemplateTests(unittest.TestCase):
    def test_renders_sale_with_and_without_total(self):
        self.assertEqual(
            render_template("venda_confirmada", {"venda": "A-10"}),
            "Venda A-10 concluida. Obrigado pela preferencia.",
        )
        texto = render_template("venda_confirmada", {"venda": "A-10", "total": "19,90"})
        self.assertIn("R$ 19,90", texto)

    def test_rejects_unknown_model_variable_and_injection(self):
        with self.assertRaises(ValueError):
            render_template("modelo_livre", {"venda": "1"})
        with self.assertRaises(ValueError):
            render_template("venda_confirmada", {})
        with self.assertRaises(ValueError):
            render_template("venda_confirmada", {"venda": "1", "promo": "oi"})
        with self.assertRaises(ValueError):
            render_template("venda_confirmada", {"venda": "1\npromo"})
        with self.assertRaises(ValueError):
            render_template("venda_confirmada", {"venda": "1", "total": "10\npromo"})


class AbuseControlTests(unittest.TestCase):
    def test_free_text_rejected_when_templates_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            config.only_templates = True
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            with self.assertRaises(InvalidMessage):
                bridge.enqueue("5511999999999", "promocao livre")
            job = bridge.enqueue(
                "5511999999999",
                None,
                template="venda_confirmada",
                variables={"venda": "9"},
            )
            self.assertEqual(job.message, "")
            self.assertIn("Venda 9", open_job(config, job)["message"])

    def test_per_number_hour_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            config.per_number_per_hour = 1
            config.per_number_per_day = 3
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            bridge.enqueue("5511999999999", "primeira")
            with self.assertRaises(RateLimited):
                bridge.enqueue("5511999999999", "segunda")
            bridge.enqueue("5511888888888", "outro numero")

    def test_duplicate_message_returns_existing_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            first = bridge.enqueue("5511999999999", "mesma mensagem")
            second = bridge.enqueue("5511999999999", "mesma mensagem")
            self.assertEqual(first.id, second.id)
            self.assertEqual(len(store.recent(50)), 1)

    def test_manual_send_bypasses_number_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            config.per_number_per_hour = 1
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            first = bridge.enqueue("5511999999999", "teste 1", manual=True)
            second = bridge.enqueue("5511999999999", "teste 2", manual=True)
            self.assertNotEqual(first.id, second.id)

    def test_sequence_is_sent_and_incremented(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            calls = []
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"ok": True})], calls),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                done = wait_for(store, job.id, {STATUS_SENT})
                self.assertEqual(done.status, STATUS_SENT)
            finally:
                bridge.stop()
            self.assertEqual(calls[0]["sequence"], 1)
            self.assertEqual(config.command_sequence, 1)


class AndroidManifestTests(unittest.TestCase):
    NS = "{http://schemas.android.com/apk/res/android}"
    PERMISSAO = "br.com.caracore.pdv.sms.permission.SMS_INTERNAL"

    def setUp(self):
        caminho = (
            Path(__file__).resolve().parents[1]
            / "android"
            / "src"
            / "main"
            / "AndroidManifest.xml"
        )
        self.root = ET.parse(caminho).getroot()

    def test_envio_externo_esta_fechado(self):
        for node in self.root.iter("activity"):
            if node.get(self.NS + "name") == ".SendSmsActivity":
                self.assertEqual(node.get(self.NS + "exported"), "false")
                self.assertEqual(node.get(self.NS + "permission"), self.PERMISSAO)
                return
        self.fail("SendSmsActivity ausente do manifesto")

    def test_permissao_interna_e_de_assinatura(self):
        for node in self.root.iter("permission"):
            if node.get(self.NS + "name") == self.PERMISSAO:
                self.assertEqual(node.get(self.NS + "protectionLevel"), "signature")
                return
        self.fail("permissao interna ausente")


class E2ETests(unittest.TestCase):
    def test_roundtrip_binds_the_job_id(self):
        private_der, public_raw = e2e.generate_keypair()
        peer = base64.b64encode(public_raw).decode("ascii")
        envelope = e2e.seal(peer, b'{"number":"1"}', b"job-1")
        self.assertEqual(e2e.open_sealed(private_der, envelope, b"job-1"), b'{"number":"1"}')
        with self.assertRaises(e2e.E2EError):
            e2e.open_sealed(private_der, envelope, b"job-2")
        tampered = bytearray(base64.b64decode(envelope))
        tampered[-1] ^= 1
        with self.assertRaises(e2e.E2EError):
            e2e.open_sealed(private_der, base64.b64encode(bytes(tampered)).decode("ascii"), b"job-1")

    def test_each_message_uses_a_new_ephemeral_key(self):
        _, public_raw = e2e.generate_keypair()
        peer = base64.b64encode(public_raw).decode("ascii")
        self.assertNotEqual(e2e.seal(peer, b"x", b"id"), e2e.seal(peer, b"x", b"id"))

    def test_tags_are_stable_and_do_not_reveal_the_value(self):
        key = b"k" * 32
        self.assertEqual(e2e.tag(key, "5511999999999"), e2e.tag(key, "5511999999999"))
        self.assertNotEqual(e2e.tag(key, "5511999999999"), e2e.tag(key, "5511888888888"))
        self.assertNotIn("5511", e2e.tag(key, "5511999999999"))

    def test_public_key_validation(self):
        public_raw = e2e.generate_keypair()[1]
        self.assertTrue(e2e.is_valid_public_key_b64(base64.b64encode(public_raw).decode("ascii")))
        self.assertFalse(e2e.is_valid_public_key_b64("abc"))
        self.assertFalse(e2e.is_valid_public_key_b64(""))
        self.assertFalse(e2e.is_valid_public_key_b64(base64.b64encode(b"\x04" + b"\x00" * 64).decode("ascii")))


class AuditTests(unittest.TestCase):
    def test_records_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(Path(tmp) / "sms_audit.jsonl")
            audit.record("fila", id="abc", destino="tag-destino", conteudo="tag-conteudo", status="fila", selado=True)
            texto = (Path(tmp) / "sms_audit.jsonl").read_text(encoding="utf-8")
            for proibido in ("number", "mensagem", "envelope", "5511999999999"):
                self.assertNotIn(proibido, texto)
            entrada = audit.entries(1)[0]
            self.assertEqual(entrada["evento"], "fila")
            self.assertEqual(entrada["destino"], "tag-destino")
            self.assertTrue(entrada["selado"])

    def test_refuses_content_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(Path(tmp) / "sms_audit.jsonl")
            with self.assertRaises(ValueError):
                audit.record("fila", mensagem="segredo")
            with self.assertRaises(ValueError):
                audit.record("fila", campo_novo="x")

    def test_purge_keeps_only_the_retention_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sms_audit.jsonl"
            audit = AuditLog(path, retention_days=90)
            velho = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
            agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            path.write_text(
                json.dumps({"ts": velho, "evento": "fila"}) + "\n" + json.dumps({"ts": agora, "evento": "enviado"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(audit.purge(), 1)
            self.assertEqual(audit.count(), 1)
            self.assertEqual(audit.entries(1)[0]["evento"], "enviado")

    def test_erase_removes_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(Path(tmp) / "sms_audit.jsonl")
            audit.record("fila", id="abc")
            audit.erase()
            self.assertEqual(audit.count(), 0)
            self.assertEqual(audit.entries(5), [])


class PrivacyTests(unittest.TestCase):
    def test_state_and_audit_never_store_the_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            job = bridge.enqueue("5511999999999", "mensagem secreta")
            estado = (Path(tmp) / "sms_state.json").read_text(encoding="utf-8")
            trilha = (Path(tmp) / "sms_audit.jsonl").read_text(encoding="utf-8")
            for texto in (estado, trilha):
                self.assertNotIn("5511999999999", texto)
                self.assertNotIn("mensagem secreta", texto)
            self.assertIn("envelope", estado)
            self.assertTrue(job.sealed)
            self.assertIn(job.recipient_tag, trilha)
            self.assertIn(job.content_tag, trilha)

    def test_rejects_send_without_phone_key_when_e2e_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            config.phone_public_key_b64 = ""
            config.save()
            bridge = SmsBridge(config, make_store(tmp), client_factory=factory([], []))
            with self.assertRaises(InvalidMessage):
                bridge.enqueue("5511999999999", "ola")

    def test_erase_history_clears_jobs_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            bridge = SmsBridge(config, store, client_factory=factory([], []))
            bridge.enqueue("5511999999999", "ola")
            self.assertGreater(store.audit.count(), 0)
            bridge.erase_history()
            self.assertEqual(store.recent(10), [])
            self.assertEqual(store.audit.count(), 0)

    def test_legacy_queued_job_is_sealed_before_sending(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            store = make_store(tmp)
            pending = SmsJob.create("5511999999999", "conteudo antigo")
            store.add(pending)
            calls = []
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"ok": True})], calls),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                done = wait_for(store, pending.id, {STATUS_SENT})
            finally:
                bridge.stop()
            self.assertTrue(done.sealed)
            self.assertEqual(done.message, "")
            self.assertEqual(open_job(config, done)["message"], "conteudo antigo")
            self.assertTrue(calls[0]["envelope"])

    def test_legacy_send_learns_the_phone_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            config.phone_public_key_b64 = ""
            config.e2e_required = False
            config.save()
            store = make_store(tmp)
            chave = base64.b64encode(e2e.generate_keypair()[1]).decode("ascii")
            calls = []
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"ok": True, "key": chave})], calls),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                wait_for(store, job.id, {STATUS_SENT})
            finally:
                bridge.stop()
            self.assertFalse(job.sealed)
            self.assertEqual(calls[0]["number"], "5511999999999")
            self.assertEqual(config.phone_key_fingerprint(), e2e.fingerprint_b64(chave))

    def test_ack_cannot_replace_a_registered_phone_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            original = config.phone_key_fingerprint()
            store = make_store(tmp)
            chave = base64.b64encode(e2e.generate_keypair()[1]).decode("ascii")
            bridge = SmsBridge(
                config,
                store,
                client_factory=factory([SendResult(True, {"ok": True, "key": chave})], []),
                retry_delay=0.01,
            )
            bridge.start()
            try:
                job = bridge.enqueue("5511999999999", "ola")
                wait_for(store, job.id, {STATUS_SENT})
            finally:
                bridge.stop()
            self.assertEqual(config.phone_key_fingerprint(), original)
            self.assertNotEqual(config.phone_key_fingerprint(), e2e.fingerprint_b64(chave))


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

    def request(
        self,
        method: str,
        path: str,
        body=None,
        token: str | None = None,
        sign: bool = True,
        timestamp: int | None = None,
        nonce: str | None = None,
        signature: str | None = None,
        sign_key: str | None = None,
        extra_headers: dict | None = None,
    ):
        connection = HTTPConnection("127.0.0.1", self.server.port, timeout=3)
        headers = dict(extra_headers or {})
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-Api-Token"] = token
        if sign and method.upper() == "POST" and path == "/api/sms":
            moment = int(time.time()) if timestamp is None else int(timestamp)
            nonce_value = nonce or secrets.token_hex(8)
            key_text = sign_key if sign_key is not None else (token or "token-de-teste")
            if signature is None:
                signature = signing.sign_request(
                    key_text.encode("utf-8"), method, path, payload or b"", moment, nonce_value
                )
            headers[signing.TIMESTAMP_HEADER] = str(moment)
            headers[signing.NONCE_HEADER] = nonce_value
            headers[signing.SIGNATURE_HEADER] = signature
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

    def test_sms_requires_signature(self):
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "5511999999999", "message": "oi"},
            token="token-de-teste",
            sign=False,
        )
        self.assertEqual(code, 401)
        self.assertIn("assinatura", data["error"])

    def test_sms_rejects_expired_signature(self):
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "5511999999999", "message": "oi"},
            token="token-de-teste",
            timestamp=int(time.time()) - 120,
        )
        self.assertEqual(code, 401)
        self.assertIn("expirada", data["error"])

    def test_sms_rejects_wrong_signature(self):
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "5511999999999", "message": "oi"},
            token="token-de-teste",
            sign_key="outra-chave",
        )
        self.assertEqual(code, 401)
        self.assertIn("invalida", data["error"])

    def test_sms_rejects_replayed_nonce(self):
        nonce = secrets.token_hex(8)
        body = {"number": "5511999999999", "message": "oi"}
        code, _ = self.request("POST", "/api/sms", body, token="token-de-teste", nonce=nonce)
        self.assertEqual(code, 202)
        code, data = self.request("POST", "/api/sms", body, token="token-de-teste", nonce=nonce)
        self.assertEqual(code, 401)
        self.assertIn("repetido", data["error"])

    def test_send_is_loopback_only(self):
        self.assertTrue(self.server.allows_send_from("127.0.0.1"))
        self.assertTrue(is_loopback_address("::1"))
        self.assertTrue(is_loopback_address("::ffff:127.0.0.1"))
        self.assertFalse(self.server.allows_send_from("192.168.0.10"))
        self.assertFalse(is_loopback_address("10.0.0.2"))
        self.assertFalse(is_loopback_address("nao-e-ip"))

    def test_template_only_rejects_free_text_and_renders_sale(self):
        self.config.only_templates = True
        code, data = self.request(
            "POST",
            "/api/sms",
            {"number": "5511999999999", "message": "promocao livre", "venda_id": "v1"},
            token="token-de-teste",
        )
        self.assertEqual(code, 400)
        self.assertIn("modelo", data["error"])
        code, data = self.request(
            "POST",
            "/api/sms",
            {
                "number": "5511999999999",
                "template": "venda_confirmada",
                "variaveis": {"venda": "123", "total": "10,50"},
                "venda_id": "v2",
            },
            token="token-de-teste",
        )
        self.assertEqual(code, 202)
        self.assertTrue(data["sealed"])
        job = self.store.get(data["id"])
        self.assertEqual(job.message, "")
        texto = open_job(self.config, job)["message"]
        self.assertIn("Venda 123", texto)
        self.assertIn("R$ 10,50", texto)

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

    def key_blob(self, public_key_b64: str) -> str:
        key = key_from_base64(self.config.shared_secret_b64)
        payload = json.dumps({"phone_public_key": public_key_b64}).encode("utf-8")
        return base64.b64encode(encrypt(key, payload)).decode("ascii")

    def test_phone_key_route_sets_first_key_and_refuses_replacement(self):
        self.config.phone_public_key_b64 = ""
        self.config.save()
        chave = base64.b64encode(e2e.generate_keypair()[1]).decode("ascii")
        code, _ = self.request("POST", "/api/mobile/key", {"blob": self.key_blob(chave)})
        self.assertEqual(code, 200)
        self.assertEqual(self.config.phone_key_fingerprint(), e2e.fingerprint_b64(chave))
        outra = base64.b64encode(e2e.generate_keypair()[1]).decode("ascii")
        code, data = self.request("POST", "/api/mobile/key", {"blob": self.key_blob(outra)})
        self.assertEqual(code, 409)
        self.assertIn("pareie", data["error"])
        self.assertEqual(self.config.phone_key_fingerprint(), e2e.fingerprint_b64(chave))

    def test_phone_key_route_rejects_clear_body(self):
        chave = base64.b64encode(e2e.generate_keypair()[1]).decode("ascii")
        code, _ = self.request("POST", "/api/mobile/key", {"phone_public_key": chave})
        self.assertEqual(code, 400)

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
        chave = base64.b64encode(e2e.generate_keypair()[1]).decode("ascii")
        code, data = self.request(
            "POST",
            "/api/mobile/diagnostic",
            {"token": token, "sms_ok": True, "battery_ok": False, "message": "", "phone_public_key": chave},
        )
        self.assertEqual(code, 200)
        self.assertTrue(data["paired"])
        self.assertEqual(self.config.phone_key_fingerprint(), e2e.fingerprint_b64(chave))
        code, _ = self.request(
            "POST",
            "/api/mobile/diagnostic",
            {"token": token, "sms_ok": True, "battery_ok": False, "message": "", "phone_public_key": chave},
        )
        self.assertEqual(code, 403)

    def test_diagnostic_without_phone_key_is_refused(self):
        token = self.config.new_setup_token()
        self.config.phone_public_key_b64 = ""
        self.config.save()
        code, data = self.request(
            "POST",
            "/api/mobile/diagnostic",
            {"token": token, "sms_ok": True, "battery_ok": True, "message": ""},
        )
        self.assertEqual(code, 400)
        self.assertIn("criptografia", data["error"])
        self.assertTrue(self.config.setup_token_valid(token))

    def test_diagnostic_rejects_broken_phone_key(self):
        token = self.config.new_setup_token()
        self.config.save()
        code, data = self.request(
            "POST",
            "/api/mobile/diagnostic",
            {"token": token, "sms_ok": True, "battery_ok": True, "message": "", "phone_public_key": "b64-invalida"},
        )
        self.assertEqual(code, 400)
        self.assertIn("chave", data["error"])


if __name__ == "__main__":
    unittest.main()
