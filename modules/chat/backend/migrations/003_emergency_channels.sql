ALTER TABLE chat_conversations
    DROP CONSTRAINT IF EXISTS chat_conversations_type_check;

ALTER TABLE chat_conversations
    ADD CONSTRAINT chat_conversations_type_check
    CHECK (type IN ('DIRECT', 'GROUP', 'INSTITUTIONAL', 'EMERGENCY'));

ALTER TABLE chat_conversations
    ADD COLUMN IF NOT EXISTS school_code VARCHAR(80) NULL;

ALTER TABLE chat_conversations
    ADD COLUMN IF NOT EXISTS managed_by_system BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE chat_conversations
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';

ALTER TABLE chat_conversations
    DROP CONSTRAINT IF EXISTS chat_conversations_status_check;

ALTER TABLE chat_conversations
    ADD CONSTRAINT chat_conversations_status_check
    CHECK (status IN ('ACTIVE', 'ARCHIVED'));

CREATE UNIQUE INDEX IF NOT EXISTS ux_chat_emergency_school_active
    ON chat_conversations(school_code)
    WHERE type = 'EMERGENCY'
      AND status = 'ACTIVE'
      AND archived_at IS NULL;

UPDATE chat_identities
SET
    organization_kind = 'ESCOLA',
    school_code = 'SCHOOL-A',
    role = 'GESTOR_ESCOLA',
    active = TRUE,
    updated_at = now()
WHERE id = 'mock:escola-a';

UPDATE chat_identities
SET
    organization_kind = 'SECRETARIA',
    school_code = NULL,
    role = 'GESTOR_SECRETARIA',
    active = TRUE,
    updated_at = now()
WHERE id = 'mock:secretaria';

UPDATE chat_identities
SET
    organization_kind = 'GUARDA',
    school_code = NULL,
    role = 'OPERADOR_GUARDA',
    active = TRUE,
    updated_at = now()
WHERE id = 'mock:guarda';

INSERT INTO chat_identities(
    id,
    display_name,
    organization_kind,
    school_code,
    role,
    active
)
VALUES
    (
        'mock:escola-b',
        'Gestor Escola B',
        'ESCOLA',
        'SCHOOL-B',
        'GESTOR_ESCOLA',
        TRUE
    )
ON CONFLICT (id) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    organization_kind = EXCLUDED.organization_kind,
    school_code = EXCLUDED.school_code,
    role = EXCLUDED.role,
    active = TRUE,
    updated_at = now();

INSERT INTO chat_conversations(
    id,
    type,
    title,
    created_by,
    school_code,
    managed_by_system,
    status
)
VALUES
    (
        'emergency:SCHOOL-A',
        'EMERGENCY',
        'Canal de Emergencia - Escola A',
        'mock:secretaria',
        'SCHOOL-A',
        TRUE,
        'ACTIVE'
    ),
    (
        'emergency:SCHOOL-B',
        'EMERGENCY',
        'Canal de Emergencia - Escola B',
        'mock:secretaria',
        'SCHOOL-B',
        TRUE,
        'ACTIVE'
    )
ON CONFLICT (id) DO UPDATE
SET
    type = EXCLUDED.type,
    title = EXCLUDED.title,
    school_code = EXCLUDED.school_code,
    managed_by_system = TRUE,
    status = 'ACTIVE',
    archived_at = NULL,
    updated_at = now();

INSERT INTO chat_conversation_members(
    conversation_id,
    identity_id,
    member_role
)
VALUES
    ('emergency:SCHOOL-A', 'mock:escola-a', 'MEMBER'),
    ('emergency:SCHOOL-A', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-A', 'mock:guarda', 'MEMBER'),

    ('emergency:SCHOOL-B', 'mock:escola-b', 'MEMBER'),
    ('emergency:SCHOOL-B', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-B', 'mock:guarda', 'MEMBER')
ON CONFLICT (conversation_id, identity_id) DO UPDATE
SET
    left_at = NULL,
    member_role = EXCLUDED.member_role;