-- EDUVIGIA_CHAT_INSTITUTIONAL_BROADCAST_007
-- Guarda/Secretaria -> todas as escolas.
-- Escolas possuem somente leitura.

BEGIN;

INSERT INTO chat_conversations(
    id,
    type,
    title,
    created_by,
    school_code,
    managed_by_system,
    status
)
VALUES (
    'institutional:ALL-SCHOOLS',
    'INSTITUTIONAL',
    'Avisos Gerais - Todas as Escolas',
    'mock:secretaria',
    NULL,
    TRUE,
    'ACTIVE'
)
ON CONFLICT (id) DO UPDATE
SET
    type = 'INSTITUTIONAL',
    title = EXCLUDED.title,
    school_code = NULL,
    managed_by_system = TRUE,
    status = 'ACTIVE',
    archived_at = NULL,
    updated_at = now();

INSERT INTO chat_conversation_members(
    conversation_id,
    identity_id,
    member_role
)
SELECT
    'institutional:ALL-SCHOOLS',
    i.id,
    CASE
        WHEN i.organization_kind IN ('GUARDA', 'SECRETARIA') THEN 'OWNER'
        ELSE 'MEMBER'
    END
FROM chat_identities i
WHERE i.active = TRUE
  AND i.organization_kind IN ('ESCOLA', 'GUARDA', 'SECRETARIA')
ON CONFLICT (conversation_id, identity_id) DO UPDATE
SET
    member_role = EXCLUDED.member_role,
    left_at = NULL;

CREATE OR REPLACE FUNCTION chat_sync_institutional_broadcast_membership()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.organization_kind IN ('ESCOLA', 'GUARDA', 'SECRETARIA') THEN
        IF NEW.active = TRUE THEN
            INSERT INTO chat_conversation_members(
                conversation_id,
                identity_id,
                member_role
            )
            SELECT
                'institutional:ALL-SCHOOLS',
                NEW.id,
                CASE
                    WHEN NEW.organization_kind IN ('GUARDA', 'SECRETARIA')
                        THEN 'OWNER'
                    ELSE 'MEMBER'
                END
            WHERE EXISTS (
                SELECT 1
                FROM chat_conversations
                WHERE id = 'institutional:ALL-SCHOOLS'
                  AND type = 'INSTITUTIONAL'
                  AND status = 'ACTIVE'
                  AND archived_at IS NULL
            )
            ON CONFLICT (conversation_id, identity_id) DO UPDATE
            SET
                member_role = EXCLUDED.member_role,
                left_at = NULL;
        ELSE
            UPDATE chat_conversation_members
            SET left_at = COALESCE(left_at, now())
            WHERE conversation_id = 'institutional:ALL-SCHOOLS'
              AND identity_id = NEW.id
              AND left_at IS NULL;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_chat_sync_institutional_broadcast_membership
ON chat_identities;

CREATE TRIGGER trg_chat_sync_institutional_broadcast_membership
AFTER INSERT OR UPDATE OF organization_kind, active
ON chat_identities
FOR EACH ROW
EXECUTE FUNCTION chat_sync_institutional_broadcast_membership();

CREATE OR REPLACE FUNCTION chat_guard_institutional_broadcast_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_org_kind TEXT;
BEGIN
    IF NEW.conversation_id = 'institutional:ALL-SCHOOLS' THEN
        SELECT organization_kind
          INTO v_org_kind
          FROM chat_identities
         WHERE id = NEW.sender_identity_id;

        IF v_org_kind IS NULL
           OR v_org_kind NOT IN ('GUARDA', 'SECRETARIA')
        THEN
            RAISE EXCEPTION
                'Identity % cannot publish to institutional broadcast',
                NEW.sender_identity_id
                USING ERRCODE = '42501';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_chat_guard_institutional_broadcast_write
ON chat_messages;

CREATE TRIGGER trg_chat_guard_institutional_broadcast_write
BEFORE INSERT OR UPDATE OF conversation_id, sender_identity_id
ON chat_messages
FOR EACH ROW
EXECUTE FUNCTION chat_guard_institutional_broadcast_write();

COMMIT;