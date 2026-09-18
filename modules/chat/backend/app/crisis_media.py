from __future__ import annotations

import hashlib
import os
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from livekit import api
from pydantic import BaseModel, Field

from app.crisis import (
    ALLOWED_OPERATOR_ORGS,
    SCHOOL_MANAGER_ROLE,
    ensure_room_scope,
    get_room,
    require_crisis_identity,
    write_audit,
)

router = APIRouter(prefix="/api/crisis", tags=["crisis-media"])

TOKEN_TTL_SECONDS = 600


class MediaTokenRequest(BaseModel):
    identity_id: str = Field(min_length=1, max_length=255)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(
            status_code=503,
            detail=f"Media foundation not configured: {name}",
        )
    return value


def _media_room_name(crisis_room_id: str) -> str:
    digest = hashlib.sha256(crisis_room_id.encode("utf-8")).hexdigest()[:32]
    return f"crisis-{digest}"


def _participant_identity(crisis_room_id: str, identity_id: str) -> str:
    raw = f"{crisis_room_id}|{identity_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:32]
    return f"participant-{digest}"


def _grants_for(identity):
    if identity["organization_kind"] == "ESCOLA":
        if identity["role"] != SCHOOL_MANAGER_ROLE:
            raise HTTPException(
                status_code=403,
                detail="Perfil escolar sem permissao de midia da Sala de Crise",
            )

        return {
            "participant_role": "SCHOOL_PUBLISHER",
            "can_publish": True,
            "can_subscribe": False,
            "can_publish_sources": ["microphone"],
        }

    if identity["organization_kind"] in ALLOWED_OPERATOR_ORGS:
        return {
            "participant_role": "OPERATOR_SUBSCRIBER",
            "can_publish": False,
            "can_subscribe": True,
            "can_publish_sources": None,
        }

    raise HTTPException(
        status_code=403,
        detail="Perfil sem permissao de midia da Sala de Crise",
    )


@router.get("/media/foundation")
async def media_foundation():
    configured = all(
        os.getenv(name, "").strip()
        for name in (
            "CRISIS_LIVEKIT_PUBLIC_URL",
            "CRISIS_LIVEKIT_API_KEY",
            "CRISIS_LIVEKIT_API_SECRET",
        )
    )

    return {
        "provider": "LIVEKIT_SELF_HOSTED",
        "configured": configured,
        "media_enabled": False,
        "phase": "V0.8-R2.1",
        "recording_enabled": False,
        "school_audio_modes": ["OFF", "PTT", "LIVE"],
    }


@router.post("/rooms/{room_id}/media/token")
async def issue_media_token(
    request: Request,
    room_id: str,
    payload: MediaTokenRequest,
):
    api_key = _required_env("CRISIS_LIVEKIT_API_KEY")
    api_secret = _required_env("CRISIS_LIVEKIT_API_SECRET")
    public_url = _required_env("CRISIS_LIVEKIT_PUBLIC_URL")

    async with request.app.state.db.acquire() as conn:
        async with conn.transaction():
            identity = await require_crisis_identity(conn, payload.identity_id)
            room = await get_room(conn, room_id)
            ensure_room_scope(identity, room)

            if room["status"] == "ENDED":
                raise HTTPException(
                    status_code=409,
                    detail="Sala de Crise encerrada",
                )

            grants = _grants_for(identity)
            room_name = _media_room_name(room_id)
            participant_identity = _participant_identity(
                room_id,
                identity["id"],
            )

            video_grants = api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=grants["can_publish"],
                can_subscribe=grants["can_subscribe"],
                can_publish_data=False,
                can_publish_sources=grants["can_publish_sources"],
            )

            token = (
                api.AccessToken(api_key, api_secret)
                .with_identity(participant_identity)
                .with_grants(video_grants)
                .with_ttl(timedelta(seconds=TOKEN_TTL_SECONDS))
                .to_jwt()
            )

            await write_audit(
                conn,
                room_id,
                identity["id"],
                "MEDIA_TOKEN_ISSUED",
                {
                    "provider": "LIVEKIT_SELF_HOSTED",
                    "participant_role": grants["participant_role"],
                    "can_publish": grants["can_publish"],
                    "can_subscribe": grants["can_subscribe"],
                    "can_publish_sources": grants["can_publish_sources"] or [],
                    "ttl_seconds": TOKEN_TTL_SECONDS,
                },
            )

    return {
        "provider": "LIVEKIT_SELF_HOSTED",
        "phase": "V0.8-R2.1",
        "server_url": public_url,
        "room_name": room_name,
        "participant_identity": participant_identity,
        "participant_role": grants["participant_role"],
        "can_publish": grants["can_publish"],
        "can_subscribe": grants["can_subscribe"],
        "can_publish_sources": grants["can_publish_sources"] or [],
        "token": token,
        "token_ttl_seconds": TOKEN_TTL_SECONDS,
        "school_audio_state": room["school_audio_state"],
        "recording_enabled": False,
        "media_enabled": False,
    }
