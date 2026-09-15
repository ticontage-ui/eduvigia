import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Set

import asyncpg
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from redis.asyncio import Redis

DATABASE_DSN = os.environ["CHAT_DATABASE_DSN"]
REDIS_URL = os.environ["CHAT_REDIS_URL"]
REDIS_CHANNEL = os.getenv("CHAT_REDIS_CHANNEL", "eduvigia:chat:events")
APP_VERSION = os.getenv("CHAT_VERSION", "0.1.0-R1")


class MessageIn(BaseModel):
    room_id: str = Field(default="general", min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=2000)


class Hub:
    def __init__(self) -> None:
        self.connections: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.lock:
            self.connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.discard(websocket)

    async def broadcast(self, message: str) -> None:
        async with self.lock:
            targets = list(self.connections)

        dead = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self.lock:
                for ws in dead:
                    self.connections.discard(ws)


hub = Hub()


def record_to_message(record: asyncpg.Record) -> dict:
    return {
        "id": record["id"],
        "room_id": record["room_id"],
        "display_name": record["display_name"],
        "body": record["body"],
        "created_at": record["created_at"].isoformat(),
    }


async def redis_listener(redis: Redis) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    try:
        async for event in pubsub.listen():
            if event.get("type") != "message":
                continue
            data = event.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            await hub.broadcast(data)
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
            # V0.1: mantemos a mensagem/outbox persistidos e tentamos novamente.
            pass

        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(
        DATABASE_DSN,
        min_size=1,
        max_size=5,
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

    redis_ok = await app.state.redis.ping()

    return {
        "status": "ok",
        "version": APP_VERSION,
        "postgres": "ok",
        "redis": "ok" if redis_ok else "fail",
        "outbox_pending": pending,
        "core_integration": "disabled",
    }


@app.get("/api/messages")
async def list_messages(room_id: str = "general", limit: int = 100):
    limit = max(1, min(limit, 200))

    async with app.state.db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, room_id, display_name, body, created_at
            FROM chat_messages
            WHERE room_id = $1
            ORDER BY id DESC
            LIMIT $2
            """,
            room_id,
            limit,
        )

    return [record_to_message(row) for row in reversed(rows)]


@app.post("/api/messages", status_code=201)
async def create_message(message: MessageIn):
    display_name = message.display_name.strip()
    body = message.body.strip()
    room_id = message.room_id.strip()

    if not display_name or not body or not room_id:
        raise HTTPException(status_code=422, detail="Campos vazios nao sao permitidos")

    async with app.state.db.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO chat_messages(room_id, display_name, body)
                VALUES ($1, $2, $3)
                RETURNING id, room_id, display_name, body, created_at
                """,
                room_id,
                display_name,
                body,
            )

            payload = {
                "type": "message.created",
                "message": record_to_message(row),
            }

            await conn.execute(
                """
                INSERT INTO chat_outbox(event_type, aggregate_id, payload)
                VALUES ($1, $2, $3::jsonb)
                """,
                "message.created",
                row["id"],
                json.dumps(payload, ensure_ascii=False),
            )

    return record_to_message(row)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "system.ready",
                "version": APP_VERSION,
            }
        )
        while True:
            # Mantem a conexao viva. Mensagens do cliente nao sao comandos nesta versao.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception:
        await hub.disconnect(websocket)
