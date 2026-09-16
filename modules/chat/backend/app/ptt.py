import asyncio
import json
import re
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict

router = APIRouter()

PTT_MAX_SECONDS = 30
PTT_FLOOR_TTL_SECONDS = 35


class PttFloorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_id: str


class PttFloorRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_id: str
    floor_id: str


async def authorize_ptt(conn, channel_id: str, identity_id: str):
    identity = await conn.fetchrow(
        """
        SELECT id, display_name, organization_kind, school_code, role
        FROM chat_identities
        WHERE id = $1
          AND active = true
        """,
        identity_id,
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Identidade sem acesso")

    channel = await conn.fetchrow(
        """
        SELECT id, type, school_code, managed_by_system, status
        FROM chat_conversations
        WHERE id = $1
        """,
        channel_id,
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Canal inexistente")

    if channel["type"] != "EMERGENCY" or not channel["managed_by_system"] or channel["status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="Canal nao autorizado para PTT")

    if identity["organization_kind"] == "ESCOLA":
        if not identity["school_code"] or identity["school_code"] != channel["school_code"]:
            raise HTTPException(status_code=403, detail="Escola nao pode acessar PTT de outra escola")

    membership = await conn.fetchrow(
        """
        SELECT conversation_id
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

    return identity, channel


class PttHub:
    def __init__(self):
        self.channels: Dict[str, Dict[WebSocket, str]] = {}
        self.lock = asyncio.Lock()
        self.timeout_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, channel_id: str, identity_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.channels.setdefault(channel_id, {})[websocket] = identity_id

    async def disconnect(self, channel_id: str, websocket: WebSocket):
        async with self.lock:
            channel = self.channels.get(channel_id)
            if not channel:
                return
            channel.pop(websocket, None)
            if not channel:
                self.channels.pop(channel_id, None)

    async def count_identity(self, channel_id: str, identity_id: str) -> int:
        async with self.lock:
            channel = self.channels.get(channel_id, {})
            return sum(1 for value in channel.values() if value == identity_id)

    async def broadcast_json(self, channel_id: str, payload: dict):
        async with self.lock:
            targets = list(self.channels.get(channel_id, {}).keys())
        dead = []
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            await self.disconnect(channel_id, websocket)

    async def broadcast_bytes(self, channel_id: str, payload: bytes, exclude: Optional[WebSocket] = None):
        async with self.lock:
            targets = list(self.channels.get(channel_id, {}).keys())
        dead = []
        for websocket in targets:
            if websocket is exclude:
                continue
            try:
                await websocket.send_bytes(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            await self.disconnect(channel_id, websocket)

    def replace_timeout(self, channel_id: str, task: asyncio.Task):
        previous = self.timeout_tasks.pop(channel_id, None)
        if previous and not previous.done():
            previous.cancel()
        self.timeout_tasks[channel_id] = task

    def cancel_timeout(self, channel_id: str):
        previous = self.timeout_tasks.pop(channel_id, None)
        if previous and not previous.done():
            previous.cancel()


hub = PttHub()


def floor_key(channel_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._:-]+", "_", channel_id)
    return f"eduvigia:ptt:floor:{safe}"


def floor_value(identity_id: str, floor_id: str) -> str:
    return json.dumps({"identity_id": identity_id, "floor_id": floor_id}, separators=(",", ":"))


async def read_floor(redis, channel_id: str):
    raw = await redis.get(floor_key(channel_id))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return json.loads(raw)
    except Exception:
        return None


async def release_floor(app, channel_id: str, identity_id: str, floor_id: str, reason: str) -> bool:
    key = floor_key(channel_id)
    expected = floor_value(identity_id, floor_id)
    deleted = await app.state.redis.eval(
        """
        local value = redis.call('get', KEYS[1])
        if value == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """,
        1,
        key,
        expected,
    )
    if deleted:
        hub.cancel_timeout(channel_id)
        await hub.broadcast_json(channel_id, {
            "type": "ptt.speaker.ended",
            "channel_id": channel_id,
            "identity_id": identity_id,
            "floor_id": floor_id,
            "reason": reason,
        })
        return True
    return False


async def timeout_floor(app, channel_id: str, identity_id: str, floor_id: str):
    try:
        await asyncio.sleep(PTT_MAX_SECONDS + 0.5)
        await release_floor(app, channel_id, identity_id, floor_id, "TIME_LIMIT")
    except asyncio.CancelledError:
        return


@router.get("/api/ptt/channels/{channel_id}/status")
async def ptt_status(request: Request, channel_id: str, identity_id: str = Query(...)):
    async with request.app.state.db.acquire() as conn:
        await authorize_ptt(conn, channel_id, identity_id)
    floor = await read_floor(request.app.state.redis, channel_id)
    return {
        "channel_id": channel_id,
        "floor": floor,
        "max_seconds": PTT_MAX_SECONDS,
        "transport": "WEBSOCKET_WEBM_OPUS",
    }


@router.post("/api/ptt/channels/{channel_id}/floor/request")
async def ptt_request_floor(request: Request, channel_id: str, payload: PttFloorRequest):
    async with request.app.state.db.acquire() as conn:
        identity, channel = await authorize_ptt(conn, channel_id, payload.identity_id)

    floor_id = "floor:" + uuid.uuid4().hex
    acquired = await request.app.state.redis.set(
        floor_key(channel_id),
        floor_value(payload.identity_id, floor_id),
        nx=True,
        ex=PTT_FLOOR_TTL_SECONDS,
    )
    if not acquired:
        return {
            "granted": False,
            "busy": True,
            "floor": await read_floor(request.app.state.redis, channel_id),
            "max_seconds": PTT_MAX_SECONDS,
        }

    task = asyncio.create_task(timeout_floor(request.app, channel_id, payload.identity_id, floor_id))
    hub.replace_timeout(channel_id, task)

    await hub.broadcast_json(channel_id, {
        "type": "ptt.speaker.started",
        "channel_id": channel_id,
        "school_code": channel["school_code"],
        "identity_id": payload.identity_id,
        "display_name": identity["display_name"],
        "organization_kind": identity["organization_kind"],
        "floor_id": floor_id,
        "max_seconds": PTT_MAX_SECONDS,
    })

    return {"granted": True, "busy": False, "floor_id": floor_id, "max_seconds": PTT_MAX_SECONDS}


@router.post("/api/ptt/channels/{channel_id}/floor/release")
async def ptt_release_floor(request: Request, channel_id: str, payload: PttFloorRelease):
    async with request.app.state.db.acquire() as conn:
        await authorize_ptt(conn, channel_id, payload.identity_id)
    released = await release_floor(request.app, channel_id, payload.identity_id, payload.floor_id, "RELEASED")
    return {"released": released, "channel_id": channel_id}


@router.websocket("/ws/ptt")
async def ptt_websocket(websocket: WebSocket, identity_id: str, channel_id: str):
    try:
        async with websocket.app.state.db.acquire() as conn:
            await authorize_ptt(conn, channel_id, identity_id)
    except HTTPException:
        await websocket.close(code=4403)
        return

    await hub.connect(channel_id, identity_id, websocket)

    try:
        await websocket.send_json({
            "type": "ptt.ready",
            "channel_id": channel_id,
            "identity_id": identity_id,
            "floor": await read_floor(websocket.app.state.redis, channel_id),
            "max_seconds": PTT_MAX_SECONDS,
        })

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            text = message.get("text")
            if text is not None:
                if text == "ping":
                    await websocket.send_text("pong")
                continue

            payload = message.get("bytes")
            if payload is None:
                continue

            floor = await read_floor(websocket.app.state.redis, channel_id)
            if not floor or floor.get("identity_id") != identity_id:
                continue

            await hub.broadcast_bytes(channel_id, payload, exclude=websocket)

    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(channel_id, websocket)
        if await hub.count_identity(channel_id, identity_id) == 0:
            floor = await read_floor(websocket.app.state.redis, channel_id)
            if floor and floor.get("identity_id") == identity_id:
                await release_floor(
                    websocket.app,
                    channel_id,
                    identity_id,
                    floor.get("floor_id", ""),
                    "DISCONNECTED",
                )