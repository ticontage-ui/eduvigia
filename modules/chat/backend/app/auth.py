from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import urllib.error
import urllib.request
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("eduvigia-chat.auth")

router = APIRouter(prefix="/api/session", tags=["commercial-session"])

SESSION_COOKIE_NAME = "__Host-eduvigia_chat"
SESSION_REDIS_PREFIX = "eduvigia:chat:session:"
WS_TICKET_REDIS_PREFIX = "eduvigia:chat:ws-ticket:"

ALLOWED_AUTH_MODES = {"standalone_qa", "core"}
CORE_ROLE_TO_ORGANIZATION = {
    "ADMIN_SECRETARIA": "SECRETARIA",
    "GESTOR_SECRETARIA": "SECRETARIA",
    "SUPERVISOR_GUARDA": "GUARDA",
    "OPERADOR_GUARDA": "GUARDA",
    "DESPACHANTE_GUARDA": "GUARDA",
    "GESTOR_ESCOLA": "ESCOLA",
    "OPERADOR_ESCOLA": "ESCOLA",
}
SCHOOL_ROLES = {"GESTOR_ESCOLA", "OPERADOR_ESCOLA"}
LEGACY_ROLE_TO_CANONICAL = {
    "ADMIN": "ADMIN_SECRETARIA",
    "SUPERVISOR": "GESTOR_SECRETARIA",
    "GESTAO": "GESTOR_SECRETARIA",
    "DESPACHANTE": "DESPACHANTE_GUARDA",
    "ESCOLA": "GESTOR_ESCOLA",
    "TECNICO": "TECNICO",
}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class WsTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Literal["CHAT", "PTT"]
    channel_id: str | None = Field(default=None, max_length=255)


class CoreAuthError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def auth_mode() -> str:
    mode = os.getenv("CHAT_AUTH_MODE", "standalone_qa").strip().lower()
    if mode not in ALLOWED_AUTH_MODES:
        raise RuntimeError(
            "CHAT_AUTH_MODE invalido; use standalone_qa ou core"
        )
    return mode


def core_base_url() -> str:
    value = os.getenv(
        "CHAT_CORE_BASE_URL",
        "http://eduvigia-core-api:8000",
    ).strip().rstrip("/")

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("CHAT_CORE_BASE_URL invalida")

    return value


def session_ttl_seconds() -> int:
    value = int(os.getenv("CHAT_SESSION_TTL_SECONDS", "120"))
    return min(max(value, 60), 900)


def ws_ticket_ttl_seconds() -> int:
    value = int(os.getenv("CHAT_WS_TICKET_TTL_SECONDS", "45"))
    return min(max(value, 15), 90)


def core_timeout_seconds() -> float:
    value = float(os.getenv("CHAT_CORE_TIMEOUT_SECONDS", "3"))
    return min(max(value, 1.0), 10.0)


def canonical_core_role(role: str, school_id=None) -> str:
    normalized = str(role or "").strip().upper()
    if normalized == "OPERADOR":
        return "OPERADOR_ESCOLA" if school_id else "OPERADOR_GUARDA"
    return LEGACY_ROLE_TO_CANONICAL.get(normalized, normalized)


def organization_for_role(role: str) -> str | None:
    return CORE_ROLE_TO_ORGANIZATION.get(str(role or "").strip().upper())


def digest_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def session_key(raw_session_id: str) -> str:
    return SESSION_REDIS_PREFIX + digest_secret(raw_session_id)


def ws_ticket_key(raw_ticket: str) -> str:
    return WS_TICKET_REDIS_PREFIX + digest_secret(raw_ticket)


def foundation_snapshot() -> dict:
    mode = auth_mode()
    return {
        "auth_mode": mode,
        "core_integration": "enabled" if mode == "core" else "prepared",
        "identity_provider": "core_session" if mode == "core" else "standalone_qa",
        "chat_password_store": False,
        "session_cookie": "HTTPONLY_SECURE_SAMESITE_STRICT",
        "session_ttl_seconds": session_ttl_seconds(),
        "session_renewal": "SLIDING_CONTEXT_REFRESH",
        "websocket_ticket": "ONE_TIME_REDIS",
        "websocket_ticket_ttl_seconds": ws_ticket_ttl_seconds(),
        "client_identity_authoritative": False if mode == "core" else True,
    }


def set_session_cookie(
    response: Response,
    raw_session_id: str,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_session_id,
        max_age=session_ttl_seconds(),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def same_origin_websocket(origin: str | None, host: str | None) -> bool:
    if not origin or not host:
        return False

    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False

    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() == host.strip().lower()
    )


def _read_json_response(response) -> dict:
    raw = response.read()
    if not raw:
        return {}

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoreAuthError(502, "Resposta invalida do Core") from exc

    if not isinstance(payload, dict):
        raise CoreAuthError(502, "Contrato invalido do Core")

    return payload


def _core_get_sync(path: str, bearer_token: str) -> dict:
    url = core_base_url() + path
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "User-Agent": "EduVigIA-Chat-Commercial-Auth/1",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=core_timeout_seconds(),
        ) as response:
            return _read_json_response(response)
    except urllib.error.HTTPError as exc:
        detail = "Sessao Core invalida ou expirada"
        try:
            body = json.loads(exc.read().decode("utf-8"))
            if isinstance(body, dict):
                detail = str(body.get("detail") or detail)
        except Exception:
            pass

        if exc.code in {401, 403}:
            raise CoreAuthError(401, detail) from exc
        if exc.code == 404:
            raise CoreAuthError(404, detail) from exc

        raise CoreAuthError(502, "Falha de autenticacao no Core") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CoreAuthError(
            503,
            "Core de autenticacao indisponivel",
        ) from exc


async def core_get(path: str, bearer_token: str) -> dict:
    try:
        return await asyncio.to_thread(
            _core_get_sync,
            path,
            bearer_token,
        )
    except CoreAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc


def bearer_from_request(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Sessao EduVigIA obrigatoria",
        )

    token = authorization[7:].strip()

    if len(token) < 20 or len(token) > 4096:
        raise HTTPException(
            status_code=401,
            detail="Sessao EduVigIA invalida",
        )

    return token


async def principal_from_core(bearer_token: str) -> dict:
    user = await core_get("/auth/me", bearer_token)

    try:
        core_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Core retornou usuario sem identificador valido",
        ) from exc

    if core_user_id <= 0:
        raise HTTPException(
            status_code=502,
            detail="Core retornou usuario invalido",
        )

    school_id = user.get("school_id")
    role = canonical_core_role(user.get("role"), school_id)
    organization_kind = organization_for_role(role)

    if not organization_kind:
        raise HTTPException(
            status_code=403,
            detail="Perfil do EduVigIA sem acesso ao Chat",
        )

    display_name = str(user.get("name") or "").strip()
    if not display_name:
        raise HTTPException(
            status_code=502,
            detail="Core retornou usuario sem nome",
        )

    school_code = None
    school_name = None

    if role in SCHOOL_ROLES:
        try:
            school_id = int(school_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=403,
                detail="Perfil escolar sem escola vinculada",
            ) from exc

        if school_id <= 0:
            raise HTTPException(
                status_code=403,
                detail="Perfil escolar sem escola vinculada",
            )

        school = await core_get(
            f"/schools/{school_id}",
            bearer_token,
        )
        school_code = str(school.get("code") or "").strip()
        school_name = str(school.get("name") or "").strip()

        if not school_code:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A escola precisa possuir codigo institucional "
                    "antes de habilitar o Chat comercial"
                ),
            )

        if len(school_code) > 80:
            raise HTTPException(
                status_code=409,
                detail="Codigo institucional da escola excede 80 caracteres",
            )
    else:
        school_id = None

    return {
        "identity_id": f"core:user:{core_user_id}",
        "core_user_id": core_user_id,
        "display_name": display_name[:80],
        "role": role,
        "organization_kind": organization_kind,
        "school_id": school_id,
        "school_code": school_code,
        "school_name": school_name,
    }


async def sync_core_identity(conn, principal: dict):
    identity_id = principal["identity_id"]
    organization_kind = principal["organization_kind"]
    school_code = principal["school_code"]

    await conn.execute(
        """
        INSERT INTO chat_identities(
            id,
            display_name,
            organization_kind,
            school_code,
            role,
            active,
            updated_at
        )
        VALUES($1,$2,$3,$4,$5,TRUE,now())
        ON CONFLICT(id) DO UPDATE
        SET
            display_name = EXCLUDED.display_name,
            organization_kind = EXCLUDED.organization_kind,
            school_code = EXCLUDED.school_code,
            role = EXCLUDED.role,
            active = TRUE,
            updated_at = now()
        """,
        identity_id,
        principal["display_name"],
        organization_kind,
        school_code,
        principal["role"],
    )

    if organization_kind == "ESCOLA":
        await conn.execute(
            """
            UPDATE chat_conversation_members cm
            SET left_at = COALESCE(cm.left_at, now())
            FROM chat_conversations c
            WHERE cm.conversation_id = c.id
              AND cm.identity_id = $1
              AND cm.left_at IS NULL
              AND c.type = 'EMERGENCY'
              AND c.school_code IS DISTINCT FROM $2
            """,
            identity_id,
            school_code,
        )

        channel_id = f"emergency:{school_code}"
        school_label = (
            principal.get("school_name")
            or school_code
        )
        title = f"Canal de Emergencia - {school_label}"[:160]

        await conn.execute(
            """
            INSERT INTO chat_conversations(
                id,
                type,
                title,
                created_by,
                school_code,
                managed_by_system,
                status
            )
            VALUES($1,'EMERGENCY',$2,$3,$4,TRUE,'ACTIVE')
            ON CONFLICT(id) DO UPDATE
            SET
                type = 'EMERGENCY',
                title = EXCLUDED.title,
                school_code = EXCLUDED.school_code,
                managed_by_system = TRUE,
                status = 'ACTIVE',
                archived_at = NULL,
                updated_at = now()
            """,
            channel_id,
            title,
            identity_id,
            school_code,
        )

        await conn.execute(
            """
            INSERT INTO chat_conversation_members(
                conversation_id,
                identity_id,
                member_role
            )
            VALUES($1,$2,'MEMBER')
            ON CONFLICT(conversation_id, identity_id) DO UPDATE
            SET left_at = NULL,
                member_role = 'MEMBER'
            """,
            channel_id,
            identity_id,
        )

        await conn.execute(
            """
            INSERT INTO chat_conversation_members(
                conversation_id,
                identity_id,
                member_role
            )
            SELECT
                $1,
                i.id,
                'OWNER'
            FROM chat_identities i
            WHERE i.active = TRUE
              AND i.organization_kind IN ('GUARDA','SECRETARIA')
            ON CONFLICT(conversation_id, identity_id) DO UPDATE
            SET left_at = NULL,
                member_role = 'OWNER'
            """,
            channel_id,
        )
    else:
        await conn.execute(
            """
            INSERT INTO chat_conversation_members(
                conversation_id,
                identity_id,
                member_role
            )
            SELECT
                c.id,
                $1,
                'OWNER'
            FROM chat_conversations c
            WHERE c.type = 'EMERGENCY'
              AND c.managed_by_system = TRUE
              AND c.status = 'ACTIVE'
              AND c.archived_at IS NULL
            ON CONFLICT(conversation_id, identity_id) DO UPDATE
            SET left_at = NULL,
                member_role = 'OWNER'
            """,
            identity_id,
        )

    await conn.execute(
        """
        INSERT INTO chat_conversation_members(
            conversation_id,
            identity_id,
            member_role
        )
        SELECT
            'institutional:ALL-SCHOOLS',
            $1,
            CASE
                WHEN $2 IN ('GUARDA','SECRETARIA')
                    THEN 'OWNER'
                ELSE 'MEMBER'
            END
        WHERE EXISTS(
            SELECT 1
            FROM chat_conversations
            WHERE id = 'institutional:ALL-SCHOOLS'
              AND type = 'INSTITUTIONAL'
              AND status = 'ACTIVE'
              AND archived_at IS NULL
        )
        ON CONFLICT(conversation_id, identity_id) DO UPDATE
        SET left_at = NULL,
            member_role = EXCLUDED.member_role
        """,
        identity_id,
        organization_kind,
    )

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
        raise HTTPException(
            status_code=403,
            detail="Identidade Chat nao pode ser ativada",
        )

    return row


async def create_commercial_session(
    request: Request,
    response: Response,
) -> dict:
    if auth_mode() != "core":
        raise HTTPException(
            status_code=409,
            detail="Exchange comercial indisponivel em modo standalone QA",
        )

    bearer = bearer_from_request(request)
    principal = await principal_from_core(bearer)

    async with request.app.state.db.acquire() as conn:
        async with conn.transaction():
            await sync_core_identity(conn, principal)

    raw_session_id = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)

    session_payload = {
        "principal": principal,
        "csrf_token": csrf_token,
    }

    await request.app.state.redis.set(
        session_key(raw_session_id),
        json.dumps(session_payload, ensure_ascii=False),
        ex=session_ttl_seconds(),
    )

    set_session_cookie(
        response,
        raw_session_id,
    )
    response.headers["Cache-Control"] = "no-store"

    return {
        "auth_mode": "core",
        "identity": principal,
        "csrf_token": csrf_token,
        "expires_in_seconds": session_ttl_seconds(),
    }


async def load_commercial_session(
    request: Request,
    *,
    require_csrf: bool | None = None,
) -> dict:
    if auth_mode() != "core":
        raise HTTPException(
            status_code=409,
            detail="Sessao comercial nao esta ativa neste runtime",
        )

    raw_session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_session_id:
        raise HTTPException(
            status_code=401,
            detail="Sessao do Chat ausente",
        )

    redis_key = session_key(raw_session_id)
    raw = await request.app.state.redis.get(
        redis_key
    )
    if not raw:
        raise HTTPException(
            status_code=401,
            detail="Sessao do Chat expirada",
        )

    try:
        session = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=401,
            detail="Sessao do Chat invalida",
        ) from exc

    if require_csrf is None:
        require_csrf = request.method.upper() in UNSAFE_METHODS

    if require_csrf:
        expected = str(session.get("csrf_token") or "")
        supplied = request.headers.get("X-CSRF-Token", "")

        if (
            not expected
            or not supplied
            or not hmac.compare_digest(expected, supplied)
        ):
            raise HTTPException(
                status_code=403,
                detail="Protecao CSRF invalida",
            )

    principal = session.get("principal")
    if not isinstance(principal, dict):
        raise HTTPException(
            status_code=401,
            detail="Sessao do Chat invalida",
        )

    await request.app.state.redis.expire(
        redis_key,
        session_ttl_seconds(),
    )

    return session


async def resolve_effective_identity(
    request: Request,
    conn,
    supplied_identity_id: str | None = None,
):
    if auth_mode() == "core":
        session = await load_commercial_session(request)
        principal = session["principal"]
        effective_id = str(principal["identity_id"])

        if (
            supplied_identity_id
            and supplied_identity_id != effective_id
        ):
            logger.warning(
                "Client identity mismatch supplied=%s effective=%s",
                supplied_identity_id,
                effective_id,
            )
            raise HTTPException(
                status_code=403,
                detail="Identidade enviada pelo cliente nao corresponde a sessao",
            )

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
            effective_id,
        )

        if not row or not row["active"]:
            raise HTTPException(
                status_code=403,
                detail="Identidade comercial inativa",
            )

        return row

    if not supplied_identity_id:
        raise HTTPException(
            status_code=422,
            detail="identity_id obrigatorio no modo standalone QA",
        )

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
        supplied_identity_id,
    )

    if not row or not row["active"]:
        raise HTTPException(
            status_code=403,
            detail="Identidade inexistente ou inativa",
        )

    return row


async def issue_ws_ticket(
    request: Request,
    payload: WsTicketRequest,
) -> dict:
    session = await load_commercial_session(
        request,
        require_csrf=True,
    )
    principal = session["principal"]

    if payload.purpose == "PTT" and not payload.channel_id:
        raise HTTPException(
            status_code=422,
            detail="channel_id obrigatorio para ticket PTT",
        )

    raw_ticket = secrets.token_urlsafe(32)
    ticket_payload = {
        "purpose": payload.purpose,
        "identity_id": principal["identity_id"],
        "channel_id": payload.channel_id,
    }

    created = await request.app.state.redis.set(
        ws_ticket_key(raw_ticket),
        json.dumps(ticket_payload, ensure_ascii=False),
        nx=True,
        ex=ws_ticket_ttl_seconds(),
    )

    if not created:
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel emitir ticket WebSocket",
        )

    return {
        "ticket": raw_ticket,
        "purpose": payload.purpose,
        "channel_id": payload.channel_id,
        "expires_in_seconds": ws_ticket_ttl_seconds(),
    }


async def consume_ws_ticket(
    websocket: WebSocket,
    *,
    expected_purpose: str,
) -> dict:
    if auth_mode() != "core":
        raise HTTPException(
            status_code=409,
            detail="Ticket WebSocket nao esta ativo no modo standalone QA",
        )

    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")

    if not same_origin_websocket(origin, host):
        raise HTTPException(
            status_code=403,
            detail="Origin WebSocket nao autorizado",
        )

    raw_ticket = websocket.query_params.get("ticket", "").strip()

    if len(raw_ticket) < 20 or len(raw_ticket) > 512:
        raise HTTPException(
            status_code=401,
            detail="Ticket WebSocket invalido",
        )

    redis_key = ws_ticket_key(raw_ticket)

    raw = await websocket.app.state.redis.eval(
        """
        local value = redis.call('GET', KEYS[1])
        if value then
            redis.call('DEL', KEYS[1])
        end
        return value
        """,
        1,
        redis_key,
    )

    if not raw:
        raise HTTPException(
            status_code=401,
            detail="Ticket WebSocket expirado ou ja utilizado",
        )

    try:
        ticket = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=401,
            detail="Ticket WebSocket invalido",
        ) from exc

    if ticket.get("purpose") != expected_purpose:
        raise HTTPException(
            status_code=403,
            detail="Ticket WebSocket para finalidade diferente",
        )

    return ticket


@router.get("/foundation")
async def session_foundation():
    return foundation_snapshot()


@router.post("/exchange")
async def session_exchange(
    request: Request,
    response: Response,
):
    return await create_commercial_session(
        request,
        response,
    )


@router.get("/context")
async def session_context(
    request: Request,
    response: Response,
):
    session = await load_commercial_session(
        request,
        require_csrf=False,
    )

    raw_session_id = request.cookies.get(
        SESSION_COOKIE_NAME
    )
    if raw_session_id:
        set_session_cookie(
            response,
            raw_session_id,
        )

    response.headers["Cache-Control"] = "no-store"

    return {
        "auth_mode": "core",
        "identity": session["principal"],
        "csrf_token": session["csrf_token"],
        "expires_in_seconds": session_ttl_seconds(),
    }


@router.post("/ws-ticket")
async def session_ws_ticket(
    request: Request,
    payload: WsTicketRequest,
):
    return await issue_ws_ticket(
        request,
        payload,
    )


@router.post("/logout")
async def session_logout(
    request: Request,
    response: Response,
):
    if auth_mode() == "core":
        raw_session_id = request.cookies.get(
            SESSION_COOKIE_NAME
        )

        if raw_session_id:
            try:
                await load_commercial_session(
                    request,
                    require_csrf=True,
                )
            except HTTPException as exc:
                if exc.status_code != 401:
                    raise

            await request.app.state.redis.delete(
                session_key(raw_session_id)
            )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"

    return {"ok": True}