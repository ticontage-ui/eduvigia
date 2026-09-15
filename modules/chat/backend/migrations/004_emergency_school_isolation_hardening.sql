-- Remove any accidental cross-school memberships that may have existed
-- from experimental V0.2 data before the emergency-domain policy.

DELETE FROM chat_conversation_members cm
USING chat_conversations c, chat_identities i
WHERE cm.conversation_id = c.id
  AND cm.identity_id = i.id
  AND c.type = 'EMERGENCY'
  AND i.organization_kind = 'ESCOLA'
  AND (
        i.school_code IS NULL
        OR c.school_code IS NULL
        OR i.school_code <> c.school_code
  );

CREATE OR REPLACE FUNCTION chat_guard_emergency_membership()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_channel_type TEXT;
    v_channel_school TEXT;
    v_org_kind TEXT;
    v_identity_school TEXT;
BEGIN
    SELECT type, school_code
      INTO v_channel_type, v_channel_school
      FROM chat_conversations
     WHERE id = NEW.conversation_id;

    SELECT organization_kind, school_code
      INTO v_org_kind, v_identity_school
      FROM chat_identities
     WHERE id = NEW.identity_id;

    IF v_channel_type = 'EMERGENCY'
       AND v_org_kind = 'ESCOLA'
       AND (
            v_identity_school IS NULL
            OR v_channel_school IS NULL
            OR v_identity_school <> v_channel_school
       )
    THEN
        RAISE EXCEPTION
            'School identity % cannot join emergency channel %',
            NEW.identity_id,
            NEW.conversation_id
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_chat_guard_emergency_membership
ON chat_conversation_members;

CREATE TRIGGER trg_chat_guard_emergency_membership
BEFORE INSERT OR UPDATE OF conversation_id, identity_id, left_at
ON chat_conversation_members
FOR EACH ROW
WHEN (NEW.left_at IS NULL)
EXECUTE FUNCTION chat_guard_emergency_membership();

-- Reassert canonical emergency memberships.
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