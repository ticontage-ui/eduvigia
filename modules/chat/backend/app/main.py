import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager, suppress
from typing import Dict, Set

import asyncpg
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from redis.asyncio import Redis

DATABASE_DSN = os.environ["CHAT_DATABASE_DSN"]
REDIS_URL = os.environ["CHAT_REDIS_URL"]
REDIS_CHANNEL = os.getenv("CHAT_REDIS_CHANNEL", "eduvigia:chat:events")
APP_VERSION = os.getenv("CHAT_VERSION", "0.2.0-R1")


class ConversationIn(BaseModel):
    type: str = Field(pattern="^(DIRECT|GROUP|INSTITUTIONAL)$")
    title: str | None = Field(default=None, max_length=160)
    created_by: str = Field(min_length=1, max_length=120)
    member_ids: list[str] = Field(min_length=1, max_length=100)


class MessageIn(BaseModel):
    sender_identity_id: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)


class ReadIn(BaseModel):
    identity_id: str = Field(min_length=1, max_length=120)
    message_id: int = Field(ge=0)


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
            targets = []
            for identity_id in audience:
                targets.extend(list(self.by_identity.get(identity_id, set())))

        dead: list[tuple[str, WebSocket]] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                for identity_id, sockets in self.by_identity.items():
                    if ws in sockets:
                        dead.append((identity_id, ws))
                        break

        for identity_id, ws in dead:
            await self.disconnect(identity_id, ws)


hub = Hub()


async def ensure_identity(conn: asyncpg.Connection, identity_id: str):
    row = await conn.fetchrow(
        """
        SELECT id, display_name, organization_kind, school_code, role, active
        FROM chat_identities
        WHERE id = $1
        """,
        identity_id,
    )
    if not row or not row["active"]:
        raise HTTPException(status_code=403, detail="Identidade inexistente ou inativa")
    return row


async def ensure_member(conn: asyncpg.Connection, conversation_id: str, identity_id: str):
    await ensure_identity(conn, identity_id)
    row = await conn.fetchrow(
        """
        SELECT conversation_id, identity_id, member_role, last_read_message_id
        FROM chat_conversation_members
        WHERE conversation_id = $1
          AND identity_id = $2
          AND left_at IS NULL
        """,
        conversation_id,
        identity_id,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Identidade nao pertence a conversa")
    return row


def message_dict(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "sender_identity_id": row["sender_identity_id"],
        "display_name": row["display_name"],
        "body": row["body"],
        "created_at": row["created_at"].isoformat(),
    }


async def redis_listener(redis: Redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    try:
        async for event in pubsub.listen():
            if event.get("type") != "message":
                continue
            raw = event.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            payload = json.loads(raw)
            audience = payload.pop("_audience", [])
            await hub.broadcast_to(audience, json.dumps(payload, ensure_ascii=False))
    finally:
        await pubsub.unsubscribe(REDIS_CHANNEL)
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
                        await app.state.redis.publish(REDIS_CHANNEL, payload)
                        await conn.execute(
                            "UPDATE chat_outbox SET published_at = now() WHERE id = $1",
                            row["id"],
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(
        DATABASE_DSN,
        min_size=1,
        max_size=10,
        command_timeout=10,
    )
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
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
    title="EduVigIA Chat Standalone",
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

    redis_ok = await app.state.redis.ping()

    return {
        "status": "ok",
        "version": APP_VERSION,
        "postgres": "ok",
        "redis": "ok" if redis_ok else "fail",
        "outbox_pending": pending,
        "migrations": migrations,
        "core_integration": "disabled",
        "identity_provider": "mock",
    }


@app.get("/api/identities")
async def list_identities():
    async with app.state.db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, display_name, organization_kind, school_code, role, active
            FROM chat_identities
            WHERE active = TRUE
            ORDER BY display_name
            """
        )
    return [dict(row) for row in rows]


@app.get("/api/conversations")
async def list_conversations(identity_id: str = Query(...)):
    async with app.state.db.acquire() as conn:
        await ensure_identity(conn, identity_id)
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.type,
                c.title,
                c.created_at,
                m.member_role,
                m.last_read_message_id,
                COALESCE(
                    (
                        SELECT max(msg.id)
                        FROM chat_messages msg
                        WHERE msg.conversation_id = c.id
                    ),
                    0
                ) AS last_message_id,
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
            WHERE c.archived_at IS NULL
            ORDER BY c.updated_at DESC, c.created_at DESC
            """,
            identity_id,
        )

        result = []
        for row in rows:
            members = await conn.fetch(
                """
                SELECT i.id, i.display_name, i.organization_kind, i.role, cm.member_role
                FROM chat_conversation_members cm
                JOIN chat_identities i ON i.id = cm.identity_id
                WHERE cm.conversation_id = $1
                  AND cm.left_at IS NULL
                ORDER BY i.display_name
                """,
                row["id"],
            )
            item = dict(row)
            item["created_at"] = row["created_at"].isoformat()
            item["members"] = [dict(member) for member in members]
            result.append(item)

    return result


@app.post("/api/conversations", status_code=201)
async def create_conversation(payload: ConversationIn):
    member_ids = list(dict.fromkeys([payload.created_by, *payload.member_ids]))

    if payload.type == "DIRECT" and len(member_ids) != 2:
        raise HTTPException(status_code=422, detail="Conversa DIRECT exige exatamente 2 membros")

    if payload.type != "DIRECT" and not payload.title:
        raise HTTPException(status_code=422, detail="Grupo/institucional exige titulo")

    conversation_id = "conv:" + uuid.uuid4().hex

    async with app.state.db.acquire() as conn:
        async with conn.transaction():
            for identity_id in member_ids:
                await ensure_identity(conn, identity_id)

            await conn.execute(
                """
                INSERT INTO chat_conversations(id, type, title, created_by)
                VALUES ($1, $2, $3, $4)
                """,
                conversation_id,
                payload.type,
                payload.title.strip() if payload.title else None,
                payload.created_by,
            )

            for identity_id in member_ids:
                await conn.execute(
                    """
                    INSERT INTO chat_conversation_members(
                        conversation_id, identity_id, member_role
                    )
                    VALUES ($1, $2, $3)
                    """,
                    conversation_id,
                    identity_id,
                    "OWNER" if identity_id == payload.created_by else "MEMBER",
                )

            event = {
                "type": "conversation.created",
                "conversation_id": conversation_id,
                "_audience": member_ids,
            }
            await conn.execute(
                """
                INSERT INTO chat_outbox(event_type, aggregate_id, payload)
                VALUES ($1, $2, $3::jsonb)
                """,
                "conversation.created",
                0,
                json.dumps(event, ensure_ascii=False),
            )

    return {
        "id": conversation_id,
        "type": payload.type,
        "title": payload.title,
        "created_by": payload.created_by,
        "member_ids": member_ids,
    }


@app.get("/api/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    identity_id: str = Query(...),
    limit: int = Query(default=100, ge=1, le=200),
):
    async with app.state.db.acquire() as conn:
        await ensure_member(conn, conversation_id, identity_id)

        rows = await conn.fetch(
            """
            SELECT
                m.id,
                m.conversation_id,
                m.sender_identity_id,
                COALESCE(i.display_name, m.display_name) AS display_name,
                m.body,
                m.created_at
            FROM chat_messages m
            LEFT JOIN chat_identities i ON i.id = m.sender_identity_id
            WHERE m.conversation_id = $1
            ORDER BY m.id DESC
            LIMIT $2
            """,
            conversation_id,
            limit,
        )

    return [message_dict(row) for row in reversed(rows)]


@app.post("/api/conversations/{conversation_id}/messages", status_code=201)
async def create_message(conversation_id: str, payload: MessageIn):
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Mensagem vazia")

    async with app.state.db.acquire() as conn:
        async with conn.transaction():
            member = await ensure_member(conn, conversation_id, payload.sender_identity_id)
            identity = await ensure_identity(conn, payload.sender_identity_id)

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
                conversation_id,
                payload.sender_identity_id,
                identity["display_name"],
                body,
            )

            audience = await conn.fetch(
                """
                SELECT identity_id
                FROM chat_conversation_members
                WHERE conversation_id = $1
                  AND left_at IS NULL
                """,
                conversation_id,
            )
            audience_ids = [item["identity_id"] for item in audience]

            await conn.execute(
                """
                UPDATE chat_conversations
                SET updated_at = now()
                WHERE id = $1
                """,
                conversation_id,
            )

            event = {
                "type": "message.created",
                "conversation_id": conversation_id,
                "message": message_dict(row),
                "_audience": audience_ids,
            }

            await conn.execute(
                """
                INSERT INTO chat_outbox(event_type, aggregate_id, payload)
                VALUES ($1, $2, $3::jsonb)
                """,
                "message.created",
                row["id"],
                json.dumps(event, ensure_ascii=False),
            )

    return message_dict(row)


@app.post("/api/conversations/{conversation_id}/read")
async def mark_read(conversation_id: str, payload: ReadIn):
    async with app.state.db.acquire() as conn:
        await ensure_member(conn, conversation_id, payload.identity_id)

        max_id = await conn.fetchval(
            """
            SELECT COALESCE(max(id), 0)
            FROM chat_messages
            WHERE conversation_id = $1
            """,
            conversation_id,
        )

        target = min(payload.message_id, max_id)

        await conn.execute(
            """
            UPDATE chat_conversation_members
            SET last_read_message_id = GREATEST(last_read_message_id, $3)
            WHERE conversation_id = $1
              AND identity_id = $2
            """,
            conversation_id,
            payload.identity_id,
            target,
        )

    return {"status": "ok", "last_read_message_id": target}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, identity_id: str = Query(...)):
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, active FROM chat_identities WHERE id = $1",
            identity_id,
        )

    if not row or not row["active"]:
        await websocket.close(code=4403)
        return

    await hub.connect(identity_id, websocket)
    try:
        await websocket.send_json(
            {
                "type": "system.ready",
                "version": APP_VERSION,
                "identity_id": identity_id,
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(identity_id, websocket)
    except Exception:
        await hub.disconnect(identity_id, websocket)