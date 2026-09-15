from contextlib import suppress
import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
import zipfile
from pathlib import Path
from contextlib import asynccontextmanager, suppress
from typing import Dict, Set

import asyncpg
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eduvigia-chat")

DATABASE_DSN = os.environ["CHAT_DATABASE_DSN"]
REDIS_URL = os.environ["CHAT_REDIS_URL"]
REDIS_CHANNEL = os.getenv("CHAT_REDIS_CHANNEL", "eduvigia:chat:events")
APP_VERSION = os.getenv("CHAT_VERSION", "0.3.0-R1")

ALLOWED_ORGANIZATIONS = {"ESCOLA", "GUARDA", "SECRETARIA"}

ATTACHMENTS_DIR = Path(os.getenv("CHAT_ATTACHMENTS_DIR", "/data/attachments"))
ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024
ATTACHMENT_MAX_FILES = 5
ATTACHMENT_MAX_TOTAL_BYTES = 50 * 1024 * 1024

ALLOWED_ATTACHMENT_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".csv": {
        "text/csv",
        "text/plain",
        "application/vnd.ms-excel",
        "application/octet-stream",
    },
}


class TextMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender_identity_id: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)


class ReadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: str = Field(min_length=1, max_length=120)
    message_id: int = Field(ge=0)


def sanitize_filename(filename: str) -> str:
    name = os.path.basename(filename or "arquivo")
    name = re.sub(r"[\x00-\x1f\x7f]+", "", name)
    name = re.sub(r"[<>:\"/\\|?*]+", "_", name)
    name = name.strip().strip(".")
    if not name:
        name = "arquivo"
    return name[:180]


def attachment_public_dict(row) -> dict:
    return {
        "id": row["id"],
        "original_name": row["original_name"],
        "mime_type": row["mime_type"],
        "extension": row["extension"],
        "size_bytes": row["size_bytes"],
        "sha256": row["sha256"],
        "validation_status": row["validation_status"],
        "created_at": row["created_at"].isoformat(),
    }


async def fetch_message_attachments(conn, message_id: int) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT
            id,
            original_name,
            mime_type,
            extension,
            size_bytes,
            sha256,
            validation_status,
            created_at
        FROM chat_attachments
        WHERE message_id = $1
        ORDER BY created_at, id
        """,
        message_id,
    )
    return [attachment_public_dict(row) for row in rows]


def validate_binary_signature(extension: str, content: bytes) -> None:
    if extension in {".jpg", ".jpeg"}:
        if not content.startswith(b"\xff\xd8\xff"):
            raise HTTPException(status_code=415, detail="Assinatura JPEG invalida")

    elif extension == ".png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(status_code=415, detail="Assinatura PNG invalida")

    elif extension == ".webp":
        if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
            raise HTTPException(status_code=415, detail="Assinatura WEBP invalida")

    elif extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="Assinatura PDF invalida")

    elif extension in {".doc", ".xls"}:
        if not content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise HTTPException(status_code=415, detail="Assinatura Office legacy invalida")

    elif extension in {".docx", ".xlsx"}:
        import io
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
                names = set(archive.namelist())

                if "[Content_Types].xml" not in names:
                    raise HTTPException(status_code=415, detail="Pacote Office invalido")

                if extension == ".docx" and not any(name.startswith("word/") for name in names):
                    raise HTTPException(status_code=415, detail="DOCX invalido")

                if extension == ".xlsx" and not any(name.startswith("xl/") for name in names):
                    raise HTTPException(status_code=415, detail="XLSX invalido")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=415, detail="Pacote Office invalido")

    elif extension in {".txt", ".csv"}:
        if b"\x00" in content[:4096]:
            raise HTTPException(status_code=415, detail="Arquivo textual invalido")


async def validate_upload(upload: UploadFile) -> tuple[str, str, bytes, str]:
    original_name = sanitize_filename(upload.filename or "arquivo")
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=415, detail="Tipo de arquivo nao permitido")

    content_type = (upload.content_type or "application/octet-stream").lower()

    if content_type not in ALLOWED_ATTACHMENT_TYPES[extension]:
        raise HTTPException(status_code=415, detail="MIME type nao permitido")

    content = await upload.read(ATTACHMENT_MAX_BYTES + 1)

    if not content:
        raise HTTPException(status_code=422, detail="Arquivo vazio")

    if len(content) > ATTACHMENT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede 25 MB")

    validate_binary_signature(extension, content)

    sha256 = hashlib.sha256(content).hexdigest()

    return original_name, extension, content, sha256

class Hub:
    def __init__(self) -> None:
        self.by_identity: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, identity_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self.lock:
            self.by_identity.setdefault(identity_id, set()).add(ws)

    async def disconnect(self, identity_id: str, ws: WebSocket) -> None:
        async with self.lock:
            sockets = self.by_identity.get(identity_id)
            if not sockets:
                return
            sockets.discard(ws)
            if not sockets:
                self.by_identity.pop(identity_id, None)

    async def broadcast_to(self, audience: list[str], message: str) -> None:
        async with self.lock:
            targets = [
                (identity_id, ws)
                for identity_id in audience
                for ws in list(self.by_identity.get(identity_id, set()))
            ]

        dead: list[tuple[str, WebSocket]] = []

        for identity_id, ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append((identity_id, ws))

        for identity_id, ws in dead:
            await self.disconnect(identity_id, ws)

    async def connection_count(self) -> int:
        async with self.lock:
            return sum(len(items) for items in self.by_identity.values())


hub = Hub()


async def get_operational_identity(conn: asyncpg.Connection, identity_id: str):
    row = await conn.fetchrow(
        """
        SELECT
            id,
            display_name,
            organization_kind,
            school_code,
            role,
            active
        FROM chat_identities
        WHERE id = $1
        """,
        identity_id,
    )

    if not row or not row["active"]:
        raise HTTPException(status_code=403, detail="Identidade inexistente ou inativa")

    if row["organization_kind"] not in ALLOWED_ORGANIZATIONS:
        raise HTTPException(status_code=403, detail="Identidade fora do dominio emergencial")

    return row


async def ensure_channel_access(
    conn: asyncpg.Connection,
    channel_id: str,
    identity_id: str,
):
    identity = await get_operational_identity(conn, identity_id)

    channel = await conn.fetchrow(
        """
        SELECT
            id,
            type,
            title,
            school_code,
            managed_by_system,
            status
        FROM chat_conversations
        WHERE id = $1
          AND type = 'EMERGENCY'
          AND managed_by_system = TRUE
          AND status = 'ACTIVE'
          AND archived_at IS NULL
        """,
        channel_id,
    )

    if not channel:
        raise HTTPException(status_code=404, detail="Canal de emergencia inexistente")

    # School isolation is evaluated BEFORE membership. Even if an erroneous
    # membership exists in the database, a school can never cross school_code.
    if identity["organization_kind"] == "ESCOLA":
        if not identity["school_code"]:
            raise HTTPException(status_code=403, detail="Escola sem vinculo institucional")

        if identity["school_code"] != channel["school_code"]:
            logger.warning(
                "Cross-school access denied identity=%s identity_school=%s channel=%s channel_school=%s",
                identity_id,
                identity["school_code"],
                channel_id,
                channel["school_code"],
            )
            raise HTTPException(
                status_code=403,
                detail="Escola nao pode acessar canal de outra escola",
            )

    membership = await conn.fetchrow(
        """
        SELECT conversation_id, identity_id, last_read_message_id
        FROM chat_conversation_members
        WHERE conversation_id = $1
          AND identity_id = $2
          AND left_at IS NULL
        """,
        channel_id,
        identity_id,
    )

    if not membership:
        raise HTTPException(status_code=403, detail="Sem acesso ao canal")

    return identity, channel, membership


def message_dict(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"],
        "channel_id": row["conversation_id"],
        "sender_identity_id": row["sender_identity_id"],
        "display_name": row["display_name"],
        "sender_organization_kind": row["sender_organization_kind"],
        "sender_role": row["sender_role"],
        "body": row["body"],
        "created_at": row["created_at"].isoformat(),
        "attachments": [],
    }


async def redis_listener(redis: Redis) -> None:
    while True:
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(REDIS_CHANNEL)

            async for event in pubsub.listen():
                if event.get("type") != "message":
                    continue

                raw = event.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                payload = json.loads(raw)
                audience = payload.pop("_audience", [])
                await hub.broadcast_to(
                    audience,
                    json.dumps(payload, ensure_ascii=False),
                )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis listener failed; reconnecting")
            await asyncio.sleep(1)
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe(REDIS_CHANNEL)
            with suppress(Exception):
                await pubsub.aclose()


async def outbox_worker(app: FastAPI) -> None:
    while True:
        try:
            async with app.state.db.acquire() as conn:
                async with conn.transaction():
                    rows = await conn.fetch(
                        """
                        SELECT id, payload
                        FROM chat_outbox
                        WHERE published_at IS NULL
                        ORDER BY id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 50
                        """
                    )

                    for row in rows:
                        payload = row["payload"]

                        if not isinstance(payload, str):
                            payload = json.dumps(payload, ensure_ascii=False)

                        await app.state.redis.publish(
                            REDIS_CHANNEL,
                            payload,
                        )

                        await conn.execute(
                            """
                            UPDATE chat_outbox
                            SET published_at = now()
                            WHERE id = $1
                            """,
                            row["id"],
                        )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Outbox worker iteration failed")

        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    app.state.db = await asyncpg.create_pool(
        DATABASE_DSN,
        min_size=1,
        max_size=10,
        command_timeout=10,
    )

    app.state.redis = Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=5,
        health_check_interval=20,
    )

    await app.state.redis.ping()

    listener = asyncio.create_task(redis_listener(app.state.redis))
    outbox = asyncio.create_task(outbox_worker(app))

    try:
        yield
    finally:
        listener.cancel()
        outbox.cancel()

        with suppress(asyncio.CancelledError):
            await listener

        with suppress(asyncio.CancelledError):
            await outbox

        await app.state.redis.aclose()
        await app.state.db.close()


app = FastAPI(
    title="EduVigIA Emergency Chat",
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    async with app.state.db.acquire() as conn:
        await conn.fetchval("SELECT 1")

        pending = await conn.fetchval(
            "SELECT count(*) FROM chat_outbox WHERE published_at IS NULL"
        )

        migrations = await conn.fetchval(
            "SELECT count(*) FROM chat_schema_migrations"
        )

        active_channels = await conn.fetchval(
            """
            SELECT count(*)
            FROM chat_conversations
            WHERE type = 'EMERGENCY'
              AND managed_by_system = TRUE
              AND status = 'ACTIVE'
              AND archived_at IS NULL
            """
        )

    redis_ok = await app.state.redis.ping()

    return {
        "status": "ok",
        "version": APP_VERSION,
        "domain": "EMERGENCY_CHANNELS",
        "text_only": True,
        "postgres": "ok",
        "redis": "ok" if redis_ok else "fail",
        "outbox_pending": pending,
        "migrations": migrations,
        "active_channels": active_channels,
        "websocket_connections": await hub.connection_count(),
        "core_integration": "disabled",
        "identity_provider": "mock",
    }


@app.get("/api/emergency/identities")
async def list_operational_identities():
    async with app.state.db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                display_name,
                organization_kind,
                school_code,
                role,
                active
            FROM chat_identities
            WHERE active = TRUE
              AND organization_kind = ANY($1::text[])
            ORDER BY
                CASE organization_kind
                    WHEN 'ESCOLA' THEN 1
                    WHEN 'GUARDA' THEN 2
                    WHEN 'SECRETARIA' THEN 3
                    ELSE 9
                END,
                display_name
            """,
            sorted(ALLOWED_ORGANIZATIONS),
        )

    return [dict(row) for row in rows]


@app.get("/api/emergency/channels")
async def list_emergency_channels(identity_id: str = Query(...)):
    async with app.state.db.acquire() as conn:
        identity = await get_operational_identity(conn, identity_id)

        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.title,
                c.school_code,
                c.status,
                c.updated_at,
                CASE
                    WHEN c.school_code = 'SCHOOL-A' THEN 'Escola A'
                    WHEN c.school_code = 'SCHOOL-B' THEN 'Escola B'
                    ELSE c.school_code
                END AS school_display_name,
                m.last_read_message_id,
                COALESCE(last_msg.id, 0) AS last_message_id,
                last_msg.body AS last_message_body,
                last_msg.created_at AS last_message_at,
                (
                    SELECT count(*)
                    FROM chat_messages msg
                    WHERE msg.conversation_id = c.id
                      AND msg.id > m.last_read_message_id
                      AND COALESCE(msg.sender_identity_id, '') <> $1
                ) AS unread_count
            FROM chat_conversations c
            JOIN chat_conversation_members m
              ON m.conversation_id = c.id
             AND m.identity_id = $1
             AND m.left_at IS NULL
            LEFT JOIN LATERAL (
                SELECT msg.id, msg.body, msg.created_at
                FROM chat_messages msg
                WHERE msg.conversation_id = c.id
                ORDER BY msg.id DESC
                LIMIT 1
            ) last_msg ON TRUE
            WHERE c.type = 'EMERGENCY'
              AND c.managed_by_system = TRUE
              AND c.status = 'ACTIVE'
              AND c.archived_at IS NULL
              AND (
                    $2 <> 'ESCOLA'
                    OR c.school_code = $3
              )
            ORDER BY
                CASE
                    WHEN (
                        SELECT count(*)
                        FROM chat_messages unread_msg
                        WHERE unread_msg.conversation_id = c.id
                          AND unread_msg.id > m.last_read_message_id
                          AND COALESCE(unread_msg.sender_identity_id, '') <> $1
                    ) > 0 THEN 0
                    ELSE 1
                END,
                COALESCE(last_msg.created_at, c.updated_at) DESC,
                c.school_code
            """,
            identity_id,
            identity["organization_kind"],
            identity["school_code"],
        )

    result = []
    for row in rows:
        item = dict(row)
        item["updated_at"] = row["updated_at"].isoformat()
        item["last_message_at"] = (
            row["last_message_at"].isoformat()
            if row["last_message_at"]
            else None
        )
        result.append(item)

    return result


@app.get("/api/emergency/channels/{channel_id}/messages")
async def list_channel_messages(
    channel_id: str,
    identity_id: str = Query(...),
    limit: int = Query(default=100, ge=1, le=200),
):
    async with app.state.db.acquire() as conn:
        await ensure_channel_access(conn, channel_id, identity_id)

        rows = await conn.fetch(
            """
            SELECT
                m.id,
                m.conversation_id,
                m.sender_identity_id,
                COALESCE(i.display_name, m.display_name) AS display_name,
                COALESCE(i.organization_kind, 'LEGACY') AS sender_organization_kind,
                COALESCE(i.role, 'LEGACY_USER') AS sender_role,
                m.body,
                m.created_at
            FROM chat_messages m
            LEFT JOIN chat_identities i
              ON i.id = m.sender_identity_id
            WHERE m.conversation_id = $1
            ORDER BY m.id DESC
            LIMIT $2
            """,
            channel_id,
            limit,
        )

        message_ids = [row["id"] for row in rows]
        attachments_by_message = {}

        if message_ids:
            attachment_rows = await conn.fetch(
                """
                SELECT
                    message_id,
                    id,
                    original_name,
                    mime_type,
                    extension,
                    size_bytes,
                    sha256,
                    validation_status,
                    created_at
                FROM chat_attachments
                WHERE message_id = ANY($1::bigint[])
                ORDER BY message_id, created_at, id
                """,
                message_ids,
            )

            for attachment_row in attachment_rows:
                message_id = attachment_row["message_id"]
                attachments_by_message.setdefault(message_id, []).append(
                    attachment_public_dict(attachment_row)
                )

    result = []

    for row in reversed(rows):
        message = message_dict(row)
        message["attachments"] = attachments_by_message.get(row["id"], [])
        result.append(message)

    return result

@app.post("/api/emergency/channels/{channel_id}/messages", status_code=201)
async def create_channel_message(
    channel_id: str,
    payload: TextMessageIn,
):
    body = payload.body.strip()

    if not body:
        raise HTTPException(status_code=422, detail="Mensagem vazia")

    async with app.state.db.acquire() as conn:
        async with conn.transaction():
            identity, channel, _ = await ensure_channel_access(
                conn,
                channel_id,
                payload.sender_identity_id,
            )

            row = await conn.fetchrow(
                """
                INSERT INTO chat_messages(
                    room_id,
                    conversation_id,
                    sender_identity_id,
                    display_name,
                    body
                )
                VALUES ($1, $1, $2, $3, $4)
                RETURNING
                    id,
                    conversation_id,
                    sender_identity_id,
                    display_name,
                    body,
                    created_at
                """,
                channel_id,
                payload.sender_identity_id,
                identity["display_name"],
                body,
            )

            await conn.execute(
                """
                UPDATE chat_conversations
                SET updated_at = now()
                WHERE id = $1
                """,
                channel_id,
            )

            audience = await conn.fetch(
                """
                SELECT identity_id
                FROM chat_conversation_members
                WHERE conversation_id = $1
                  AND left_at IS NULL
                """,
                channel_id,
            )

            audience_ids = [item["identity_id"] for item in audience]

            message = {
                "id": row["id"],
                "channel_id": row["conversation_id"],
                "sender_identity_id": row["sender_identity_id"],
                "display_name": identity["display_name"],
                "sender_organization_kind": identity["organization_kind"],
                "sender_role": identity["role"],
                "body": row["body"],
                "created_at": row["created_at"].isoformat(),
            }

            event = {
                "type": "emergency.message.created",
                "channel_id": channel_id,
                "school_code": channel["school_code"],
                "message": message,
                "_audience": audience_ids,
            }

            await conn.execute(
                """
                INSERT INTO chat_outbox(
                    event_type,
                    aggregate_id,
                    payload
                )
                VALUES ($1, $2, $3::jsonb)
                """,
                "emergency.message.created",
                row["id"],
                json.dumps(event, ensure_ascii=False),
            )

    return message


@app.post("/api/emergency/channels/{channel_id}/messages-with-attachments", status_code=201)
async def create_channel_message_with_attachments(
    channel_id: str,
    sender_identity_id: str = Form(...),
    body: str = Form(default=""),
    files: list[UploadFile] = File(...),
):
    body = body.strip()

    if not files:
        raise HTTPException(status_code=422, detail="Nenhum anexo enviado")

    if len(files) > ATTACHMENT_MAX_FILES:
        raise HTTPException(status_code=413, detail="Maximo de 5 anexos por mensagem")

    validated = []
    total_bytes = 0

    for upload in files:
        original_name, extension, content, sha256 = await validate_upload(upload)
        total_bytes += len(content)

        if total_bytes > ATTACHMENT_MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="Anexos excedem 50 MB por mensagem")

        validated.append(
            {
                "original_name": original_name,
                "extension": extension,
                "mime_type": (upload.content_type or "application/octet-stream").lower(),
                "content": content,
                "sha256": sha256,
            }
        )

    async with app.state.db.acquire() as conn:
        identity, channel, _ = await ensure_channel_access(
            conn,
            channel_id,
            sender_identity_id,
        )

        saved_paths = []

        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO chat_messages(
                        room_id,
                        conversation_id,
                        sender_identity_id,
                        display_name,
                        body
                    )
                    VALUES ($1, $1, $2, $3, $4)
                    RETURNING
                        id,
                        conversation_id,
                        sender_identity_id,
                        display_name,
                        body,
                        created_at
                    """,
                    channel_id,
                    sender_identity_id,
                    identity["display_name"],
                    body,
                )

                attachments = []

                for item in validated:
                    attachment_id = "att:" + uuid.uuid4().hex
                    stored_name = uuid.uuid4().hex + item["extension"]

                    channel_folder = ATTACHMENTS_DIR / re.sub(
                        r"[^A-Za-z0-9._-]+",
                        "_",
                        channel_id,
                    )
                    channel_folder.mkdir(parents=True, exist_ok=True)

                    storage_path = channel_folder / stored_name
                    storage_path.write_bytes(item["content"])
                    saved_paths.append(storage_path)

                    attachment_row = await conn.fetchrow(
                        """
                        INSERT INTO chat_attachments(
                            id,
                            message_id,
                            channel_id,
                            uploader_identity_id,
                            original_name,
                            stored_name,
                            mime_type,
                            extension,
                            size_bytes,
                            sha256,
                            storage_path,
                            validation_status
                        )
                        VALUES (
                            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'TYPE_VALIDATED'
                        )
                        RETURNING
                            id,
                            original_name,
                            mime_type,
                            extension,
                            size_bytes,
                            sha256,
                            validation_status,
                            created_at
                        """,
                        attachment_id,
                        row["id"],
                        channel_id,
                        sender_identity_id,
                        item["original_name"],
                        stored_name,
                        item["mime_type"],
                        item["extension"],
                        len(item["content"]),
                        item["sha256"],
                        str(storage_path),
                    )

                    attachments.append(attachment_public_dict(attachment_row))

                await conn.execute(
                    """
                    UPDATE chat_conversations
                    SET updated_at = now()
                    WHERE id = $1
                    """,
                    channel_id,
                )

                audience = await conn.fetch(
                    """
                    SELECT identity_id
                    FROM chat_conversation_members
                    WHERE conversation_id = $1
                      AND left_at IS NULL
                    """,
                    channel_id,
                )

                audience_ids = [item["identity_id"] for item in audience]

                message = {
                    "id": row["id"],
                    "channel_id": row["conversation_id"],
                    "sender_identity_id": row["sender_identity_id"],
                    "display_name": identity["display_name"],
                    "sender_organization_kind": identity["organization_kind"],
                    "sender_role": identity["role"],
                    "body": row["body"],
                    "created_at": row["created_at"].isoformat(),
                    "attachments": attachments,
                }

                event = {
                    "type": "emergency.message.created",
                    "channel_id": channel_id,
                    "school_code": channel["school_code"],
                    "message": message,
                    "_audience": audience_ids,
                }

                await conn.execute(
                    """
                    INSERT INTO chat_outbox(event_type, aggregate_id, payload)
                    VALUES ($1, $2, $3::jsonb)
                    """,
                    "emergency.message.created",
                    row["id"],
                    json.dumps(event, ensure_ascii=False),
                )

            return message

        except Exception:
            for path in saved_paths:
                with suppress(Exception):
                    path.unlink()
            raise


@app.get("/api/emergency/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: str,
    identity_id: str = Query(...),
):
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                channel_id,
                original_name,
                mime_type,
                storage_path
            FROM chat_attachments
            WHERE id = $1
            """,
            attachment_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Anexo inexistente")

        await ensure_channel_access(
            conn,
            row["channel_id"],
            identity_id,
        )

    path = Path(row["storage_path"])

    if not path.is_file():
        raise HTTPException(status_code=410, detail="Arquivo nao encontrado no storage")

    return FileResponse(
        path=path,
        media_type=row["mime_type"],
        filename=row["original_name"],
    )

@app.post("/api/emergency/channels/{channel_id}/read")
async def mark_channel_read(
    channel_id: str,
    payload: ReadIn,
):
    async with app.state.db.acquire() as conn:
        await ensure_channel_access(
            conn,
            channel_id,
            payload.identity_id,
        )

        max_id = await conn.fetchval(
            """
            SELECT COALESCE(max(id), 0)
            FROM chat_messages
            WHERE conversation_id = $1
            """,
            channel_id,
        )

        target = min(payload.message_id, max_id)

        await conn.execute(
            """
            UPDATE chat_conversation_members
            SET last_read_message_id = GREATEST(
                last_read_message_id,
                $3
            )
            WHERE conversation_id = $1
              AND identity_id = $2
            """,
            channel_id,
            payload.identity_id,
            target,
        )

    return {
        "status": "ok",
        "last_read_message_id": target,
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    identity_id: str = Query(...),
):
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, active, organization_kind
            FROM chat_identities
            WHERE id = $1
            """,
            identity_id,
        )

    if (
        not row
        or not row["active"]
        or row["organization_kind"] not in ALLOWED_ORGANIZATIONS
    ):
        await websocket.close(code=4403)
        return

    await hub.connect(identity_id, websocket)

    try:
        await websocket.send_json(
            {
                "type": "system.ready",
                "version": APP_VERSION,
                "domain": "EMERGENCY_CHANNELS",
                "identity_id": identity_id,
            }
        )

        while True:
            message = await websocket.receive_text()

            if message == "ping":
                await websocket.send_json({"type": "system.pong"})

    except WebSocketDisconnect:
        await hub.disconnect(identity_id, websocket)

    except Exception:
        logger.exception(
            "WebSocket error for identity=%s",
            identity_id,
        )
        await hub.disconnect(identity_id, websocket)