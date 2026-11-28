"""Fila SQLite do Gaspar 2.0: a unica dona do estado de cada pedido.

Regras que fazem o isolamento entre PDV e Hub funcionar:

- toda leitura e escrita carrega a origem; um pedido do PDV nunca aparece para o
  Hub, nem pelo identificador, nem pelo ``id_externo``, nem na trilha;
- o contador de notificacoes e por origem, entao o cursor de um produto nao
  revela quanto o outro esta mandando;
- numero do cliente, texto do SMS e ``id_externo`` so existem cifrados no banco.

A fila da uma unica chance automatica por pedido e trata ``incerto`` como estado
que espera decisao humana: ela nao reenvia sozinha e nao troca de meio sozinha.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from .errors import InvalidRequest, QueueFull, StorageError, UnknownMessage
from .model import (
    EVENTO_CRIADA,
    EVENTO_ENTREGUE,
    EVENTO_ENVIADA,
    EVENTO_FALHA,
    EVENTO_INCERTA,
    EVENTO_RECEBIDA,
    ORIGENS,
    STATUS_ENTREGUE,
    STATUS_ENVIANDO,
    STATUS_ENVIADO,
    STATUS_FALHOU,
    STATUS_FILA,
    STATUS_INCERTO,
    Event,
    Inbound,
    Message,
    MessageBrief,
    normalizar_destino,
    normalizar_identificador,
    normalizar_texto,
    validar_origem,
)
from .transport import InboundReply
from .vault import Vault

SCHEMA_VERSION = 1
DOMAIN_EXTERNAL = "id_externo"
DOMAIN_RECIPIENT = "destino"
MAX_MOTIVO = 200

_EVENT_BY_STATUS = {
    STATUS_ENVIADO: EVENTO_ENVIADA,
    STATUS_ENTREGUE: EVENTO_ENTREGUE,
    STATUS_FALHOU: EVENTO_FALHA,
    STATUS_INCERTO: EVENTO_INCERTA,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    origem TEXT NOT NULL CHECK (origem IN ('PDV', 'HUB')),
    external_id_enc TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    recipient_enc TEXT NOT NULL,
    recipient_tag TEXT NOT NULL,
    text_enc TEXT NOT NULL,
    status TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    transport TEXT NOT NULL DEFAULT '',
    device_id TEXT NOT NULL DEFAULT '',
    reference TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    sent_at REAL NOT NULL DEFAULT 0,
    delivered_at REAL NOT NULL DEFAULT 0,
    finished_at REAL NOT NULL DEFAULT 0,
    UNIQUE (origem, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_messages_claim ON messages (origem, status, created_at);
CREATE INDEX IF NOT EXISTS ix_messages_external ON messages (origem, external_id_enc, created_at);
CREATE INDEX IF NOT EXISTS ix_messages_recipient ON messages (recipient_tag, created_at);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origem TEXT NOT NULL,
    origin_seq INTEGER NOT NULL,
    message_id TEXT NOT NULL,
    event TEXT NOT NULL,
    status TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    transport TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE (origem, origin_seq)
);

CREATE TABLE IF NOT EXISTS counters (
    origem TEXT PRIMARY KEY,
    seq INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inbounds (
    id TEXT PRIMARY KEY,
    transport TEXT NOT NULL,
    device_id TEXT NOT NULL DEFAULT '',
    sender_enc TEXT NOT NULL,
    sender_tag TEXT NOT NULL,
    text_enc TEXT NOT NULL,
    reference TEXT NOT NULL DEFAULT '',
    received_at REAL NOT NULL,
    origem TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    routed_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_inbounds_pending ON inbounds (origem, received_at);
"""


def _day_start(now: float | None = None) -> float:
    moment = datetime.fromtimestamp(time.time() if now is None else now).astimezone()
    return moment.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _motivo(texto: object) -> str:
    return str(texto or "").strip()[:MAX_MOTIVO]


def _external_plaintext(origem: str, external_id: str) -> str:
    """O id_externo e cifrado junto com a origem: dois produtos que avisam o mesmo
    numero de venda nao podem ser ligados por quem le o arquivo da fila."""
    return f"{origem}|{external_id}"


def _external_lido(origem: str, blob: str, vault: Vault) -> str:
    texto = vault.reveal(blob, DOMAIN_EXTERNAL)
    prefixo = f"{origem}|"
    return texto[len(prefixo) :] if texto.startswith(prefixo) else texto


class MessageStore:
    """Fila persistida em SQLite, com leitura e escrita sempre amarradas a uma origem."""

    def __init__(self, path: Path, vault: Vault, *, max_pending: int = 2000):
        self.path = Path(path)
        self.vault = vault
        self.max_pending = max(1, int(max_pending))
        self._lock = threading.RLock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        except sqlite3.Error as exc:
            raise StorageError("nao foi possivel abrir a fila do Gaspar") from exc
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
            self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    # ------------------------------------------------------------------ util

    @property
    def handle(self) -> sqlite3.Connection:
        """Conexao da fila. Uso de dentro do pacote, sempre sob ``lock``."""
        return self._conn

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            origem=row["origem"],
            external_id=_external_lido(row["origem"], row["external_id_enc"], self.vault),
            idempotency_key=row["idempotency_key"],
            recipient=self.vault.open(row["recipient_enc"]),
            text=self.vault.open(row["text_enc"]),
            status=row["status"],
            motivo=row["motivo"],
            transport=row["transport"],
            device_id=row["device_id"],
            attempts=int(row["attempts"] or 0),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            sent_at=float(row["sent_at"]),
            delivered_at=float(row["delivered_at"]),
            finished_at=float(row["finished_at"]),
            recipient_tag=row["recipient_tag"],
        )

    def _raw_message(self, message_id: str, origem: str) -> sqlite3.Row | None:
        """A linha do pedido, vista so pela origem dele (D1)."""
        cursor = self._conn.execute(
            "SELECT * FROM messages WHERE id = ? AND origem = ?", (message_id, origem)
        )
        return cursor.fetchone()

    # ------------------------------------------------------------- escrever

    def enqueue(
        self,
        *,
        origem: str,
        external_id: str,
        recipient: str,
        text: str,
        idempotency_key: str = "",
    ) -> tuple[Message, bool]:
        """Guarda um pedido. Devolve (pedido, criado_agora) - repeticao achata no mesmo id."""
        try:
            origin = validar_origem(origem)
            external = normalizar_identificador(external_id, "id_externo", 64)
            number = normalizar_destino(recipient)
            body = normalizar_texto(text)
            key = str(idempotency_key or "").strip() or uuid.uuid4().hex
            key = normalizar_identificador(key, "chave_repeticao", 96)
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc

        now = time.time()
        record = (
            uuid.uuid4().hex,
            origin,
            self.vault.deterministic(_external_plaintext(origin, external), DOMAIN_EXTERNAL),
            key,
            self.vault.seal(number),
            self.vault.tag(number, DOMAIN_RECIPIENT),
            self.vault.seal(body),
            STATUS_FILA,
            now,
            now,
        )
        with self._lock, self._conn:
            pending = self._conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE origem = ? AND status IN (?, ?)",
                (origin, STATUS_FILA, STATUS_ENVIANDO),
            ).fetchone()["n"]
            if pending >= self.max_pending:
                raise QueueFull("fila cheia: resolva os pedidos pendentes antes de enviar mais")
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO messages (id, origem, external_id_enc, idempotency_key,"
                " recipient_enc, recipient_tag, text_enc, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                record,
            )
            if cursor.rowcount == 0:
                existing = self._conn.execute(
                    "SELECT * FROM messages WHERE origem = ? AND idempotency_key = ?",
                    (origin, key),
                ).fetchone()
                if existing is None:  # pragma: no cover - protecao contra banco estranho
                    raise StorageError("a fila perdeu o rastro do pedido repetido")
                return self._row_to_message(existing), False
            message_id = record[0]
            self._add_event(origin, message_id, EVENTO_CRIADA, STATUS_FILA, "", "")
        message = self.get(origin, message_id)
        if message is None:  # pragma: no cover - recem-inserido
            raise StorageError("o pedido nao ficou guardado na fila")
        return message, True

    def claim_next(self, origem: str) -> Message | None:
        """Pega o pedido mais antigo na fila daquela origem e marca como em envio."""
        origin = validar_origem(origem)
        now = time.time()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id FROM messages WHERE origem = ? AND status = ?"
                " ORDER BY created_at, id LIMIT 1",
                (origin, STATUS_FILA),
            ).fetchone()
            if row is None:
                return None
            updated = self._conn.execute(
                "UPDATE messages SET status = ?, attempts = attempts + 1, updated_at = ?"
                " WHERE id = ? AND status = ?",
                (STATUS_ENVIANDO, now, row["id"], STATUS_FILA),
            )
            if updated.rowcount != 1:  # pragma: no cover - so com concorrencia externa
                return None
        return self.get(origin, row["id"])

    def mark(
        self,
        message_id: str,
        status: str,
        *,
        origem: str,
        motivo: str = "",
        transport: str = "",
        device_id: str = "",
        reference: str = "",
    ) -> Message | None:
        """Muda o estado do pedido e escreve a notificacao correspondente.

        O pedido de outra origem e invisivel aqui (D1): sem a origem certa, o
        resultado e o mesmo de um identificador que nunca existiu.
        """
        origin = validar_origem(origem)
        with self._lock, self._conn:
            row = self._raw_message(message_id, origin)
            if row is None:
                return None
            now = time.time()
            changes: dict[str, object] = {
                "status": status,
                "motivo": _motivo(motivo),
                "updated_at": now,
            }
            if transport:
                changes["transport"] = transport
            if device_id:
                changes["device_id"] = device_id
            if reference:
                changes["reference"] = reference
            if status == STATUS_ENVIADO and not row["sent_at"]:
                changes["sent_at"] = now
            if status == STATUS_ENTREGUE:
                changes["delivered_at"] = now
                changes["finished_at"] = now
            if status in (STATUS_FALHOU, STATUS_INCERTO):
                changes["finished_at"] = now
            assignments = ", ".join(f"{column} = ?" for column in changes)
            self._conn.execute(
                f"UPDATE messages SET {assignments} WHERE id = ? AND origem = ?",
                (*changes.values(), message_id, origin),
            )
            fresh = self._raw_message(message_id, origin)
            event = _EVENT_BY_STATUS.get(status)
            if event is not None:
                self._add_event(origin, message_id, event, status, motivo, transport)
        return None if fresh is None else self._row_to_message(fresh)

    def resolve_uncertain(
        self,
        message_id: str,
        status: str,
        *,
        origem: str,
        motivo: str = "conferido no painel",
    ) -> Message:
        """Decisao do operador sobre um pedido incerto: entregue ou falhou, nada de reenvio."""
        origin = validar_origem(origem)
        if status not in (STATUS_ENTREGUE, STATUS_FALHOU):
            raise InvalidRequest("um envio incerto so pode virar entregue ou falhou")
        with self._lock, self._conn:
            row = self._raw_message(message_id, origin)
            if row is None:
                raise UnknownMessage("pedido nao encontrado")
            if row["status"] != STATUS_INCERTO:
                raise InvalidRequest("somente um envio incerto pode ser conferido assim")
            result = self.mark(message_id, status, origem=origin, motivo=motivo, transport=row["transport"])
        if result is None:  # pragma: no cover - a linha existia um instante antes
            raise UnknownMessage("pedido nao encontrado")
        return result

    def reconcile_after_restart(self) -> int:
        """Abre o que ficou travado em 'enviando' e devolve para conferencia humana.

        Na volta de um corte de energia o Gaspar nao sabe se o SMS saiu. Reenviar
        duplica mensagem e cobranca, entao o pedido vira 'incerto'.
        """
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT id, origem FROM messages WHERE status = ?", (STATUS_ENVIANDO,)
            ).fetchall()
            for row in rows:
                self.mark(
                    row["id"],
                    STATUS_INCERTO,
                    origem=row["origem"],
                    motivo="queda antes da confirmacao",
                )
        return len(rows)

    # -------------------------------------------------------------- ler

    def get(self, origem: str, message_id: str) -> Message | None:
        """Le o pedido so para a origem dele: para o outro produto e como se nao existisse."""
        origin = validar_origem(origem)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM messages WHERE id = ? AND origem = ?", (message_id, origin)
            ).fetchone()
        return None if row is None else self._row_to_message(row)

    def get_by_external(self, origem: str, external_id: str) -> Message | None:
        origin = validar_origem(origem)
        try:
            external = normalizar_identificador(external_id, "id_externo", 64)
        except ValueError as exc:
            raise InvalidRequest(str(exc)) from exc
        blob = self.vault.deterministic(_external_plaintext(origin, external), DOMAIN_EXTERNAL)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM messages WHERE origem = ? AND external_id_enc = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (origin, blob),
            ).fetchone()
        return None if row is None else self._row_to_message(row)

    def counts(self, origem: str | None = None) -> dict[str, int]:
        origin = validar_origem(origem) if origem else None
        with self._lock:
            if origin is None:
                rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM messages GROUP BY status")
            else:
                rows = self._conn.execute(
                    "SELECT status, COUNT(*) AS n FROM messages WHERE origem = ? GROUP BY status",
                    (origin,),
                )
            result = dict.fromkeys(
                (STATUS_FILA, STATUS_ENVIANDO, STATUS_ENVIADO, STATUS_ENTREGUE, STATUS_FALHOU, STATUS_INCERTO),
                0,
            )
            for row in rows:
                if row["status"] in result:
                    result[row["status"]] = int(row["n"])
            return result

    def day_count(self, origem: str) -> int:
        """Quantos pedidos esta origem abriu desde a meia-noite dela."""
        return self._count_since(origem, _day_start())

    def minute_count(self, origem: str, *, now: float | None = None) -> int:
        """Quantos pedidos esta origem abriu nos ultimos 60 segundos (D3)."""
        return self._count_since(origem, (time.time() if now is None else float(now)) - 60.0)

    def _count_since(self, origem: str, since: float) -> int:
        origin = validar_origem(origem)
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE origem = ? AND created_at >= ?",
                (origin, since),
            ).fetchone()
        return int(row["n"])

    def unowned_inbound_count(self) -> int:
        """Respostas que ainda esperam dono. Nao pertencem a nenhum produto ainda."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM inbounds WHERE origem = ''"
            ).fetchone()
        return int(row["n"])

    def stats(self) -> dict:
        return {
            "por_origem": {origem: self.counts(origem) for origem in ORIGENS},
            "respostas_por_identificar": self.unowned_inbound_count(),
        }

    # --------------------------------------------------- trilha de notificacoes

    def _add_event(
        self,
        origem: str,
        message_id: str,
        event: str,
        status: str,
        motivo: str,
        transport: str,
    ) -> int:
        """Incrementa o contador daquela origem. O cursor de um produto nunca ve o outro."""
        self._conn.execute(
            "INSERT INTO counters (origem, seq) VALUES (?, 0) ON CONFLICT(origem) DO NOTHING",
            (origem,),
        )
        self._conn.execute("UPDATE counters SET seq = seq + 1 WHERE origem = ?", (origem,))
        seq = int(
            self._conn.execute("SELECT seq FROM counters WHERE origem = ?", (origem,)).fetchone()["seq"]
        )
        self._conn.execute(
            "INSERT INTO events (origem, origin_seq, message_id, event, status, motivo, transport,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (origem, seq, message_id, event, status, _motivo(motivo), transport, time.time()),
        )
        return seq

    def add_event(self, origem: str, message_id: str, event: str, *, motivo: str = "") -> int:
        with self._lock, self._conn:
            return self._add_event(validar_origem(origem), message_id, event, "", _motivo(motivo), "")

    def events_since(self, origem: str, cursor: int = 0, limit: int = 50) -> list[Event]:
        origin = validar_origem(origem)
        start = max(0, int(cursor))
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE origem = ? AND origin_seq > ?"
                " ORDER BY origin_seq LIMIT ?",
                (origin, start, max(1, min(int(limit), 200))),
            ).fetchall()
        events: list[Event] = []
        for row in rows:
            message = self._raw_message(row["message_id"], row["origem"])
            external = ""
            if message is not None:
                external = _external_lido(row["origem"], message["external_id_enc"], self.vault)
            events.append(
                Event(
                    seq=int(row["origin_seq"]),
                    message_id=row["message_id"],
                    event=row["event"],
                    status=row["status"],
                    motivo=row["motivo"],
                    transport=row["transport"],
                    created_at=float(row["created_at"]),
                    external_id=external,
                )
            )
        return events

    # ------------------------------------------------------ respostas recebidas

    def record_inbound(self, reply: InboundReply, *, transport: str = "", text: str | None = None) -> tuple[Inbound, bool]:
        """Guarda o que chegou do meio fisico. Repeticao do mesmo aparelho nao duplica."""
        sender = ""
        try:
            sender = normalizar_destino(reply.sender)
        except ValueError:
            sender = ""
        body = str(reply.text if text is None else text or "")
        device = str(reply.device_id or "")
        name = str(transport or "")
        seed = "|".join((name, device, self.vault.tag(sender, DOMAIN_RECIPIENT), body, str(reply.reference)))
        inbound_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        record = (
            inbound_id,
            name,
            device,
            self.vault.seal(sender),
            self.vault.tag(sender, DOMAIN_RECIPIENT),
            self.vault.seal(body),
            str(reply.reference or "")[:64],
            float(reply.received_at or time.time()),
        )
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO inbounds (id, transport, device_id, sender_enc, sender_tag,"
                " text_enc, reference, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                record,
            )
            created = cursor.rowcount == 1
        inbound = Inbound(
            id=inbound_id,
            transport=name,
            device_id=device,
            sender_tag=record[4],
            text=body,
            received_at=record[7],
            sender=sender,
            reference=record[6],
        )
        return inbound, created

    def pending_inbound(self, limit: int = 50) -> list[Inbound]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM inbounds WHERE origem = '' ORDER BY received_at DESC LIMIT ?",
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [self._row_to_inbound(row, with_text=True) for row in rows]

    def inbound_for(self, origem: str, limit: int = 50) -> list[Inbound]:
        """So as respostas que ja tem dono e que sao do produto que esta perguntando."""
        origin = validar_origem(origem)
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM inbounds WHERE origem = ? ORDER BY received_at DESC LIMIT ?",
                (origin, max(1, min(int(limit), 200))),
            ).fetchall()
        return [self._row_to_inbound(row, with_text=True) for row in rows]

    def get_inbound(self, inbound_id: str, *, origem: str | None = None) -> Inbound | None:
        """Le uma resposta.

        Sem origem, e a leitura do proprio motor (a resposta ainda nao tem dono).
        Com origem, so enxerga o que ainda espera um dono e o que ja e dela (D1):
        a resposta roteada para o outro produto nao aparece.
        """
        origin = validar_origem(origem) if origem else None
        with self._lock:
            if origin is None:
                row = self._conn.execute(
                    "SELECT * FROM inbounds WHERE id = ?", (inbound_id,)
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM inbounds WHERE id = ? AND origem IN ('', ?)",
                    (inbound_id, origin),
                ).fetchone()
        return None if row is None else self._row_to_inbound(row, with_text=True)

    def _row_to_inbound(self, row: sqlite3.Row, *, with_text: bool = False) -> Inbound:
        return Inbound(
            id=row["id"],
            transport=row["transport"],
            device_id=row["device_id"],
            sender_tag=row["sender_tag"],
            text=self.vault.open(row["text_enc"]) if with_text else "",
            received_at=float(row["received_at"]),
            origem=row["origem"],
            message_id=row["message_id"],
            routed_at=float(row["routed_at"]),
            sender=self.vault.open(row["sender_enc"]) if with_text else "",
        )

    def candidates(self, recipient_tag: str, *, window: float = 86400, limit: int = 5) -> list[MessageBrief]:
        """Pedidos para aquele numero que ainda podem ser o dono de uma resposta."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, origem, external_id_enc, created_at, status FROM messages"
                " WHERE recipient_tag = ? AND created_at >= ? AND status NOT IN (?, ?)"
                " ORDER BY created_at DESC LIMIT ?",
                (
                    recipient_tag,
                    time.time() - max(60.0, float(window)),
                    STATUS_FALHOU,
                    STATUS_FILA,
                    max(1, min(int(limit), 20)),
                ),
            ).fetchall()
        return [
            MessageBrief(
                id=row["id"],
                origem=row["origem"],
                external_id=_external_lido(row["origem"], row["external_id_enc"], self.vault),
                created_at=float(row["created_at"]),
                status=row["status"],
            )
            for row in rows
        ]

    def route_inbound(self, inbound_id: str, origem: str, message_id: str, *, motivo: str = "") -> Inbound | None:
        """Entrega uma resposta ao produto dono do pedido. So funciona em mensagem ainda sem dono."""
        origin = validar_origem(origem)
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM inbounds WHERE id = ?", (inbound_id,)).fetchone()
            if row is None or row["origem"]:
                return None
            message = self._conn.execute(
                "SELECT id, origem FROM messages WHERE id = ? AND origem = ?", (message_id, origin)
            ).fetchone()
            if message is None:
                raise UnknownMessage("o pedido indicado nao pertence a essa origem")
            self._conn.execute(
                "UPDATE inbounds SET origem = ?, message_id = ?, routed_at = ? WHERE id = ?",
                (origin, message_id, time.time(), inbound_id),
            )
            self._add_event(
                origin,
                message_id,
                EVENTO_RECEBIDA,
                self._raw_message(message_id, origin)["status"],
                _motivo(motivo) or "resposta do cliente",
                row["transport"],
            )
            fresh = self._conn.execute("SELECT * FROM inbounds WHERE id = ?", (inbound_id,)).fetchone()
        return self._row_to_inbound(fresh)
