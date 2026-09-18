from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/crisis", tags=["crisis-room"])

SCHOOL_MANAGER_ROLE = "GESTOR_ESCOLA"
ALLOWED_OPERATOR_ORGS = {"GUARDA", "SECRETARIA"}
ROOM_STATUSES = {"READY", "ACTIVE", "ENDED"}


class CreateRoomRequest(BaseModel):
    identity_id: str = Field(min_length=1, max_length=255)
    incident_id: str | None = Field(default=None, max_length=255)
    incident_source: str | None = Field(default=None, max_length=80)
    external_reference: str | None = Field(default=None, max_length=255)
    triggered_at: datetime | None = None


class IdentityActionRequest(BaseModel):
    identity_id: str = Field(min_length=1, max_length=255)


async def get_identity(conn, identity_id: str):
    row = await conn.fetchrow(
        """
        SELECT
            id,
            display_name,
            role,
            organization_kind,
            school_code,
            active
        FROM chat_identities
        WHERE id = $1
        """,
        identity_id,
    )

    if not row or not row["active"]:
        raise HTTPException(status_code=401, detail="Identidade operacional invalida")

    return row


def can_access_crisis(identity) -> bool:
    if identity["organization_kind"] == "ESCOLA":
        return identity["role"] == SCHOOL_MANAGER_ROLE and bool(identity["school_code"])

    return identity["organization_kind"] in ALLOWED_OPERATOR_ORGS


def can_create_room(identity) -> bool:
    return (
        identity["organization_kind"] == "ESCOLA"
        and identity["role"] == SCHOOL_MANAGER_ROLE
        and bool(identity["school_code"])
    )


async def require_crisis_identity(conn, identity_id: str):
    identity = await get_identity(conn, identity_id)

    if not can_access_crisis(identity):
        raise HTTPException(
            status_code=403,
            detail="Perfil sem acesso a Sala de Crise",
        )

    return identity


async def get_room(conn, room_id: str):
    room = await conn.fetchrow(
        """
        SELECT *
        FROM chat_crisis_rooms
        WHERE id = $1
        """,
        room_id,
    )

    if not room:
        raise HTTPException(status_code=404, detail="Sala de Crise inexistente")

    return room


def ensure_room_scope(identity, room):
    if identity["organization_kind"] == "ESCOLA":
        if identity["role"] != SCHOOL_MANAGER_ROLE:
            raise HTTPException(status_code=403, detail="Perfil escolar sem acesso")

        if identity["school_code"] != room["school_code"]:
            raise HTTPException(
                status_code=403,
                detail="Gestor escolar nao pode acessar Sala de Crise de outra escola",
            )


async def write_audit(
    conn,
    room_id: str,
    actor_identity_id: str | None,
    action: str,
    details: dict[str, Any] | None = None,
):
    await conn.execute(
        """
        INSERT INTO chat_crisis_room_audit(
            room_id,
            actor_identity_id,
            action,
            details
        )
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        room_id,
        actor_identity_id,
        action,
        json.dumps(details or {}, ensure_ascii=False),
    )


def dt(value):
    return value.isoformat() if value else None


def room_dict(row):
    return {
        "id": row["id"],
        "school_code": row["school_code"],
        "status": row["status"],
        "incident_id": row["incident_id"],
        "incident_source": row["incident_source"],
        "external_reference": row["external_reference"],
        "triggered_by_identity_id": row["triggered_by_identity_id"],
        "triggered_at": dt(row["triggered_at"]),
        "school_audio_state": row["school_audio_state"],
        "school_audio_publisher_identity_id": row[
            "school_audio_publisher_identity_id"
        ],
        "school_audio_started_at": dt(row["school_audio_started_at"]),
        "school_audio_stopped_at": dt(row["school_audio_stopped_at"]),
        "created_by_identity_id": row["created_by_identity_id"],
        "created_at": dt(row["created_at"]),
        "updated_at": dt(row["updated_at"]),
        "ended_at": dt(row["ended_at"]),
        "active_participants": int(row.get("active_participants", 0)),
    }


@router.get("/context")
async def crisis_context(
    request: Request,
    identity_id: str = Query(...),
):
    async with request.app.state.db.acquire() as conn:
        identity = await get_identity(conn, identity_id)

    return {
        "identity_id": identity["id"],
        "display_name": identity["display_name"],
        "role": identity["role"],
        "organization_kind": identity["organization_kind"],
        "school_code": identity["school_code"],
        "can_access": can_access_crisis(identity),
        "can_create": can_create_room(identity),
        "can_publish_school_audio": can_create_room(identity),
        "media_enabled": False,
        "recording_enabled": False,
    }


@router.get("/rooms")
async def list_rooms(
    request: Request,
    identity_id: str = Query(...),
    include_ended: bool = Query(default=False),
):
    async with request.app.state.db.acquire() as conn:
        identity = await require_crisis_identity(conn, identity_id)

        params: list[Any] = [include_ended]

        school_filter = ""
        if identity["organization_kind"] == "ESCOLA":
            school_filter = "AND r.school_code = $2"
            params.append(identity["school_code"])

        rows = await conn.fetch(
            f"""
            SELECT
                r.*,
                (
                    SELECT count(*)
                    FROM chat_crisis_room_participants p
                    WHERE p.room_id = r.id
                      AND p.left_at IS NULL
                ) AS active_participants
            FROM chat_crisis_rooms r
            WHERE ($1 = TRUE OR r.status <> 'ENDED')
              {school_filter}
            ORDER BY
                CASE r.status
                    WHEN 'ACTIVE' THEN 0
                    WHEN 'READY' THEN 1
                    ELSE 2
                END,
                COALESCE(r.triggered_at, r.created_at) DESC
            """,
            *params,
        )

    return [room_dict(row) for row in rows]


@router.post("/rooms", status_code=201)
async def create_room(
    request: Request,
    payload: CreateRoomRequest,
):
    async with request.app.state.db.acquire() as conn:
        async with conn.transaction():
            identity = await require_crisis_identity(conn, payload.identity_id)

            if not can_create_room(identity):
                raise HTTPException(
                    status_code=403,
                    detail="Somente GESTOR_ESCOLA pode abrir Sala de Crise manual",
                )

            if payload.incident_id:
                existing = await conn.fetchrow(
                    """
                    SELECT
                        r.*,
                        (
                            SELECT count(*)
                            FROM chat_crisis_room_participants p
                            WHERE p.room_id = r.id
                              AND p.left_at IS NULL
                        ) AS active_participants
                    FROM chat_crisis_rooms r
                    WHERE COALESCE(r.incident_source, 'UNKNOWN')
                          = COALESCE($1, 'UNKNOWN')
                      AND r.incident_id = $2
                    LIMIT 1
                    """,
                    payload.incident_source,
                    payload.incident_id,
                )

                if existing:
                    ensure_room_scope(identity, existing)
                    return room_dict(existing)

            room_id = f"crisis:{uuid4()}"
            triggered_at = payload.triggered_at or datetime.now(timezone.utc)

            await conn.execute(
                """
                INSERT INTO chat_crisis_rooms(
                    id,
                    school_code,
                    status,
                    incident_id,
                    incident_source,
                    external_reference,
                    triggered_by_identity_id,
                    triggered_at,
                    school_audio_state,
                    created_by_identity_id
                )
                VALUES (
                    $1,
                    $2,
                    'READY',
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    'OFF',
                    $6
                )
                """,
                room_id,
                identity["school_code"],
                payload.incident_id,
                payload.incident_source,
                payload.external_reference,
                identity["id"],
                triggered_at,
            )

            await write_audit(
                conn,
                room_id,
                identity["id"],
                "ROOM_CREATED",
                {
                    "school_code": identity["school_code"],
                    "incident_id": payload.incident_id,
                    "incident_source": payload.incident_source,
                    "manual": payload.incident_id is None,
                },
            )

            row = await conn.fetchrow(
                """
                SELECT r.*, 0::bigint AS active_participants
                FROM chat_crisis_rooms r
                WHERE r.id = $1
                """,
                room_id,
            )

    return room_dict(row)


@router.get("/rooms/{room_id}")
async def room_detail(
    request: Request,
    room_id: str,
    identity_id: str = Query(...),
):
    async with request.app.state.db.acquire() as conn:
        identity = await require_crisis_identity(conn, identity_id)
        room = await get_room(conn, room_id)
        ensure_room_scope(identity, room)

        row = await conn.fetchrow(
            """
            SELECT
                r.*,
                (
                    SELECT count(*)
                    FROM chat_crisis_room_participants p
                    WHERE p.room_id = r.id
                      AND p.left_at IS NULL
                ) AS active_participants
            FROM chat_crisis_rooms r
            WHERE r.id = $1
            """,
            room_id,
        )

        participants = await conn.fetch(
            """
            SELECT
                p.identity_id,
                i.display_name,
                i.role,
                i.organization_kind,
                i.school_code,
                p.joined_at,
                p.left_at
            FROM chat_crisis_room_participants p
            JOIN chat_identities i
              ON i.id = p.identity_id
            WHERE p.room_id = $1
            ORDER BY p.joined_at ASC
            """,
            room_id,
        )

    result = room_dict(row)
    result["participants"] = [
        {
            "identity_id": p["identity_id"],
            "display_name": p["display_name"],
            "role": p["role"],
            "organization_kind": p["organization_kind"],
            "school_code": p["school_code"],
            "joined_at": dt(p["joined_at"]),
            "left_at": dt(p["left_at"]),
        }
        for p in participants
    ]
    return result


@router.post("/rooms/{room_id}/join")
async def join_room(
    request: Request,
    room_id: str,
    payload: IdentityActionRequest,
):
    async with request.app.state.db.acquire() as conn:
        async with conn.transaction():
            identity = await require_crisis_identity(conn, payload.identity_id)
            room = await get_room(conn, room_id)
            ensure_room_scope(identity, room)

            if room["status"] == "ENDED":
                raise HTTPException(status_code=409, detail="Sala de Crise encerrada")

            existing = await conn.fetchrow(
                """
                SELECT id
                FROM chat_crisis_room_participants
                WHERE room_id = $1
                  AND identity_id = $2
                  AND left_at IS NULL
                LIMIT 1
                """,
                room_id,
                identity["id"],
            )

            if not existing:
                await conn.execute(
                    """
                    INSERT INTO chat_crisis_room_participants(
                        room_id,
                        identity_id,
                        joined_at,
                        last_seen_at
                    )
                    VALUES ($1, $2, now(), now())
                    """,
                    room_id,
                    identity["id"],
                )

                await write_audit(
                    conn,
                    room_id,
                    identity["id"],
                    "PARTICIPANT_JOINED",
                    {
                        "organization_kind": identity["organization_kind"],
                        "role": identity["role"],
                    },
                )

            await conn.execute(
                """
                UPDATE chat_crisis_rooms
                SET
                    status = 'ACTIVE',
                    updated_at = now()
                WHERE id = $1
                  AND status <> 'ENDED'
                """,
                room_id,
            )

            row = await conn.fetchrow(
                """
                SELECT
                    r.*,
                    (
                        SELECT count(*)
                        FROM chat_crisis_room_participants p
                        WHERE p.room_id = r.id
                          AND p.left_at IS NULL
                    ) AS active_participants
                FROM chat_crisis_rooms r
                WHERE r.id = $1
                """,
                room_id,
            )

    return room_dict(row)


@router.post("/rooms/{room_id}/leave")
async def leave_room(
    request: Request,
    room_id: str,
    payload: IdentityActionRequest,
):
    async with request.app.state.db.acquire() as conn:
        async with conn.transaction():
            identity = await require_crisis_identity(conn, payload.identity_id)
            room = await get_room(conn, room_id)
            ensure_room_scope(identity, room)

            changed = await conn.execute(
                """
                UPDATE chat_crisis_room_participants
                SET
                    left_at = now(),
                    last_seen_at = now()
                WHERE room_id = $1
                  AND identity_id = $2
                  AND left_at IS NULL
                """,
                room_id,
                identity["id"],
            )

            if changed != "UPDATE 0":
                await write_audit(
                    conn,
                    room_id,
                    identity["id"],
                    "PARTICIPANT_LEFT",
                )

            active_count = await conn.fetchval(
                """
                SELECT count(*)
                FROM chat_crisis_room_participants
                WHERE room_id = $1
                  AND left_at IS NULL
                """,
                room_id,
            )

            if room["status"] != "ENDED" and active_count == 0:
                await conn.execute(
                    """
                    UPDATE chat_crisis_rooms
                    SET
                        status = 'READY',
                        updated_at = now()
                    WHERE id = $1
                    """,
                    room_id,
                )

            row = await conn.fetchrow(
                """
                SELECT
                    r.*,
                    (
                        SELECT count(*)
                        FROM chat_crisis_room_participants p
                        WHERE p.room_id = r.id
                          AND p.left_at IS NULL
                    ) AS active_participants
                FROM chat_crisis_rooms r
                WHERE r.id = $1
                """,
                room_id,
            )

    return room_dict(row)


@router.post("/rooms/{room_id}/end")
async def end_room(
    request: Request,
    room_id: str,
    payload: IdentityActionRequest,
):
    async with request.app.state.db.acquire() as conn:
        async with conn.transaction():
            identity = await require_crisis_identity(conn, payload.identity_id)
            room = await get_room(conn, room_id)
            ensure_room_scope(identity, room)

            if room["status"] != "ENDED":
                await conn.execute(
                    """
                    UPDATE chat_crisis_rooms
                    SET
                        status = 'ENDED',
                        ended_at = now(),
                        updated_at = now(),
                        school_audio_state = 'OFF',
                        school_audio_publisher_identity_id = NULL,
                        school_audio_stopped_at = now()
                    WHERE id = $1
                    """,
                    room_id,
                )

                await conn.execute(
                    """
                    UPDATE chat_crisis_room_participants
                    SET
                        left_at = COALESCE(left_at, now()),
                        last_seen_at = now()
                    WHERE room_id = $1
                      AND left_at IS NULL
                    """,
                    room_id,
                )

                await write_audit(
                    conn,
                    room_id,
                    identity["id"],
                    "ROOM_ENDED",
                )

            row = await conn.fetchrow(
                """
                SELECT r.*, 0::bigint AS active_participants
                FROM chat_crisis_rooms r
                WHERE r.id = $1
                """,
                room_id,
            )

    return room_dict(row)
