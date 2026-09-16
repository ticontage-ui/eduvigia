import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

router = APIRouter()

PTT_MAX_SECONDS = 30
PTT_FLOOR_TTL_SECONDS = 35
PTT_RECORDINGS_DIR = Path(
    os.getenv(
        "CHAT_PTT_RECORDINGS_DIR",
        "/data/attachments/ptt-recordings",
    )
)
PTT_RECORDING_MAX_BYTES = 8 * 1024 * 1024


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


class PttRecordingManager:
    def __init__(self):
        self.sessions = {}
        self.lock = asyncio.Lock()

    async def start(
        self,
        app,
        channel_id: str,
        identity_id: str,
        floor_id: str,
    ):
        PTT_RECORDINGS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        recording_id = "pttrec:" + uuid.uuid4().hex
        stored_name = uuid.uuid4().hex + ".webm"
        final_path = PTT_RECORDINGS_DIR / stored_name
        temp_path = PTT_RECORDINGS_DIR / (stored_name + ".part")

        async with app.state.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_ptt_recordings
                SET status = 'ABORTED',
                    ended_at = COALESCE(ended_at, now()),
                    end_reason = COALESCE(end_reason, 'RECOVERY')
                WHERE status = 'RECORDING'
                  AND started_at < now() - interval '2 minutes'
                """
            )

            await conn.execute(
                """
                INSERT INTO chat_ptt_recordings(
                    id,
                    floor_id,
                    channel_id,
                    speaker_identity_id,
                    mime_type,
                    stored_name,
                    storage_path,
                    status
                )
                VALUES($1,$2,$3,$4,$5,$6,$7,'RECORDING')
                """,
                recording_id,
                floor_id,
                channel_id,
                identity_id,
                "audio/webm;codecs=opus",
                stored_name,
                str(final_path),
            )

        async with self.lock:
            self.sessions[floor_id] = {
                "id": recording_id,
                "channel_id": channel_id,
                "identity_id": identity_id,
                "temp_path": str(temp_path),
                "final_path": str(final_path),
                "sha256": hashlib.sha256(),
                "size_bytes": 0,
                "started_monotonic": time.monotonic(),
                "overflow": False,
            }

    async def append(
        self,
        floor_id: str,
        payload: bytes,
    ):
        if not floor_id or not payload:
            return

        async with self.lock:
            session = self.sessions.get(floor_id)

            if not session:
                return

            projected = (
                session["size_bytes"]
                + len(payload)
            )

            if projected > PTT_RECORDING_MAX_BYTES:
                session["overflow"] = True
                return

            with open(
                session["temp_path"],
                "ab",
            ) as handle:
                handle.write(payload)

            session["sha256"].update(payload)
            session["size_bytes"] = projected

    async def finalize(
        self,
        app,
        floor_id: str,
        reason: str,
    ):
        if not floor_id:
            return

        async with self.lock:
            session = self.sessions.pop(
                floor_id,
                None,
            )

        if not session:
            return

        temp_path = Path(session["temp_path"])
        final_path = Path(session["final_path"])

        duration_ms = int(
            max(
                0,
                min(
                    PTT_MAX_SECONDS * 1000,
                    (
                        time.monotonic()
                        - session["started_monotonic"]
                    ) * 1000,
                ),
            )
        )

        ready = (
            session["size_bytes"] > 0
            and not session["overflow"]
        )

        if ready:
            if temp_path.exists():
                os.replace(
                    str(temp_path),
                    str(final_path),
                )

            digest = session["sha256"].hexdigest()

            async with app.state.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE chat_ptt_recordings
                    SET size_bytes = $2,
                        sha256 = $3,
                        ended_at = now(),
                        duration_ms = $4,
                        end_reason = $5,
                        status = 'READY'
                    WHERE id = $1
                    """,
                    session["id"],
                    session["size_bytes"],
                    digest,
                    duration_ms,
                    reason,
                )
        else:
            try:
                temp_path.unlink(
                    missing_ok=True,
                )
            except TypeError:
                if temp_path.exists():
                    temp_path.unlink()

            async with app.state.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE chat_ptt_recordings
                    SET size_bytes = $2,
                        ended_at = now(),
                        duration_ms = $3,
                        end_reason = $4,
                        status = 'ABORTED'
                    WHERE id = $1
                    """,
                    session["id"],
                    session["size_bytes"],
                    duration_ms,
                    (
                        "SIZE_LIMIT"
                        if session["overflow"]
                        else reason
                    ),
                )


recording_manager = PttRecordingManager()

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

        try:
            await recording_manager.finalize(
                app,
                floor_id,
                reason,
            )
        except Exception:
            # Recording failure must never leave the radio floor locked.
            pass

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

    try:
        await recording_manager.start(
            request.app,
            channel_id,
            payload.identity_id,
            floor_id,
        )
    except Exception:
        await request.app.state.redis.delete(
            floor_key(channel_id)
        )
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel iniciar a gravacao PTT",
        )

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


@router.get("/api/ptt/channels/{channel_id}/recordings")
async def ptt_recording_history(
    request: Request,
    channel_id: str,
    identity_id: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
):
    async with request.app.state.db.acquire() as conn:
        await authorize_ptt(
            conn,
            channel_id,
            identity_id,
        )

        rows = await conn.fetch(
            """
            SELECT
                r.id,
                r.floor_id,
                r.channel_id,
                r.speaker_identity_id,
                i.display_name AS speaker_display_name,
                i.organization_kind,
                r.mime_type,
                r.size_bytes,
                r.sha256,
                r.started_at,
                r.ended_at,
                r.duration_ms,
                r.end_reason
            FROM chat_ptt_recordings r
            JOIN chat_identities i
              ON i.id = r.speaker_identity_id
            WHERE r.channel_id = $1
              AND r.status = 'READY'
            ORDER BY r.started_at DESC
            LIMIT $2
            """,
            channel_id,
            limit,
        )

    return [
        {
            "id": row["id"],
            "floor_id": row["floor_id"],
            "channel_id": row["channel_id"],
            "speaker_identity_id": row["speaker_identity_id"],
            "speaker_display_name": row["speaker_display_name"],
            "organization_kind": row["organization_kind"],
            "mime_type": row["mime_type"],
            "size_bytes": row["size_bytes"],
            "sha256": row["sha256"],
            "started_at": row["started_at"].isoformat(),
            "ended_at": (
                row["ended_at"].isoformat()
                if row["ended_at"]
                else None
            ),
            "duration_ms": row["duration_ms"],
            "end_reason": row["end_reason"],
        }
        for row in rows
    ]


@router.get("/api/ptt/recordings/{recording_id}/audio")
async def ptt_recording_audio(
    request: Request,
    recording_id: str,
    identity_id: str = Query(...),
):
    async with request.app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                channel_id,
                mime_type,
                storage_path,
                stored_name,
                status
            FROM chat_ptt_recordings
            WHERE id = $1
            """,
            recording_id,
        )

        if not row or row["status"] != "READY":
            raise HTTPException(
                status_code=404,
                detail="Gravacao PTT inexistente",
            )

        await authorize_ptt(
            conn,
            row["channel_id"],
            identity_id,
        )

    base = PTT_RECORDINGS_DIR.resolve()
    target = Path(
        row["storage_path"]
    ).resolve()

    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Storage PTT invalido",
        )

    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail="Arquivo de audio indisponivel",
        )

    return FileResponse(
        path=str(target),
        media_type=row["mime_type"],
        filename=row["stored_name"],
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

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

            await recording_manager.append(
                floor.get("floor_id", ""),
                payload,
            )

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