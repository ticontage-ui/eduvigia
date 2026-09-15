CREATE TABLE IF NOT EXISTS chat_identities (
    id TEXT PRIMARY KEY,
    display_name VARCHAR(80) NOT NULL,
    organization_kind VARCHAR(30) NOT NULL DEFAULT 'DEVELOPMENT',
    school_code VARCHAR(80) NULL,
    role VARCHAR(80) NOT NULL DEFAULT 'USER',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,
    type VARCHAR(20) NOT NULL
        CHECK (type IN ('DIRECT', 'GROUP', 'INSTITUTIONAL')),
    title VARCHAR(160) NULL,
    created_by TEXT NULL REFERENCES chat_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS chat_conversation_members (
    conversation_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    identity_id TEXT NOT NULL REFERENCES chat_identities(id),
    member_role VARCHAR(20) NOT NULL DEFAULT 'MEMBER'
        CHECK (member_role IN ('OWNER', 'MEMBER')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at TIMESTAMPTZ NULL,
    last_read_message_id BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (conversation_id, identity_id)
);

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS conversation_id TEXT NOT NULL DEFAULT 'general';

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS sender_identity_id TEXT NULL;

CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_id_id
    ON chat_messages(conversation_id, id);

INSERT INTO chat_identities(id, display_name, organization_kind, role)
VALUES
    ('mock:diego', 'Diego', 'DEVELOPMENT', 'DEV_B'),
    ('mock:alex', 'Alex', 'DEVELOPMENT', 'DEV_A'),
    ('mock:secretaria', 'Operador Secretaria', 'SECRETARIA', 'OPERADOR_SECRETARIA'),
    ('mock:guarda', 'Operador Guarda', 'GUARDA', 'OPERADOR_GUARDA'),
    ('mock:escola-a', 'Gestor Escola A', 'ESCOLA', 'GESTOR_ESCOLA')
ON CONFLICT (id) DO NOTHING;

INSERT INTO chat_conversations(id, type, title, created_by)
VALUES
    ('general', 'GROUP', 'Sala Geral de Desenvolvimento', 'mock:diego'),
    ('direct-diego-alex', 'DIRECT', NULL, 'mock:diego'),
    ('operacao-teste', 'INSTITUTIONAL', 'OperaÃ§Ã£o Teste', 'mock:secretaria')
ON CONFLICT (id) DO NOTHING;

INSERT INTO chat_conversation_members(conversation_id, identity_id, member_role)
VALUES
    ('general', 'mock:diego', 'OWNER'),
    ('general', 'mock:alex', 'MEMBER'),
    ('general', 'mock:secretaria', 'MEMBER'),
    ('general', 'mock:guarda', 'MEMBER'),
    ('general', 'mock:escola-a', 'MEMBER'),

    ('direct-diego-alex', 'mock:diego', 'OWNER'),
    ('direct-diego-alex', 'mock:alex', 'MEMBER'),

    ('operacao-teste', 'mock:secretaria', 'OWNER'),
    ('operacao-teste', 'mock:guarda', 'MEMBER'),
    ('operacao-teste', 'mock:diego', 'MEMBER'),
    ('operacao-teste', 'mock:alex', 'MEMBER')
ON CONFLICT (conversation_id, identity_id) DO NOTHING;

UPDATE chat_messages
SET conversation_id = COALESCE(NULLIF(room_id, ''), 'general')
WHERE conversation_id = 'general';

INSERT INTO chat_identities(id, display_name, organization_kind, role)
SELECT DISTINCT
    'legacy:' || md5(lower(trim(display_name))),
    trim(display_name),
    'LEGACY',
    'LEGACY_USER'
FROM chat_messages
WHERE sender_identity_id IS NULL
  AND trim(display_name) <> ''
ON CONFLICT (id) DO NOTHING;

UPDATE chat_messages
SET sender_identity_id = 'legacy:' || md5(lower(trim(display_name)))
WHERE sender_identity_id IS NULL
  AND trim(display_name) <> '';