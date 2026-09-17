-- EduVigIA Chat
-- QA-only seed: 10 additional schools for standalone testing.
-- DO NOT convert this file into a production migration.
--
-- Result:
--   10 QA schools
--   20 school identities
--   10 emergency channels
--   40 active memberships
--
-- Existing SCHOOL-A, SCHOOL-B, Guarda and Secretaria are preserved.

BEGIN;

INSERT INTO chat_identities(
    id,
    display_name,
    organization_kind,
    school_code,
    role,
    active
)
VALUES
    ('mock:gestor-escola-01', 'Gestor Escola Teste 01', 'ESCOLA', 'SCHOOL-01', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-01', 'Operador Câmeras Escola Teste 01', 'ESCOLA', 'SCHOOL-01', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-02', 'Gestor Escola Teste 02', 'ESCOLA', 'SCHOOL-02', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-02', 'Operador Câmeras Escola Teste 02', 'ESCOLA', 'SCHOOL-02', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-03', 'Gestor Escola Teste 03', 'ESCOLA', 'SCHOOL-03', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-03', 'Operador Câmeras Escola Teste 03', 'ESCOLA', 'SCHOOL-03', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-04', 'Gestor Escola Teste 04', 'ESCOLA', 'SCHOOL-04', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-04', 'Operador Câmeras Escola Teste 04', 'ESCOLA', 'SCHOOL-04', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-05', 'Gestor Escola Teste 05', 'ESCOLA', 'SCHOOL-05', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-05', 'Operador Câmeras Escola Teste 05', 'ESCOLA', 'SCHOOL-05', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-06', 'Gestor Escola Teste 06', 'ESCOLA', 'SCHOOL-06', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-06', 'Operador Câmeras Escola Teste 06', 'ESCOLA', 'SCHOOL-06', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-07', 'Gestor Escola Teste 07', 'ESCOLA', 'SCHOOL-07', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-07', 'Operador Câmeras Escola Teste 07', 'ESCOLA', 'SCHOOL-07', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-08', 'Gestor Escola Teste 08', 'ESCOLA', 'SCHOOL-08', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-08', 'Operador Câmeras Escola Teste 08', 'ESCOLA', 'SCHOOL-08', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-09', 'Gestor Escola Teste 09', 'ESCOLA', 'SCHOOL-09', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-09', 'Operador Câmeras Escola Teste 09', 'ESCOLA', 'SCHOOL-09', 'OPERADOR_ESCOLA', TRUE),
    ('mock:gestor-escola-10', 'Gestor Escola Teste 10', 'ESCOLA', 'SCHOOL-10', 'GESTOR_ESCOLA', TRUE),
    ('mock:operador-escola-10', 'Operador Câmeras Escola Teste 10', 'ESCOLA', 'SCHOOL-10', 'OPERADOR_ESCOLA', TRUE)
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
    ('emergency:SCHOOL-01', 'EMERGENCY', 'Canal de Emergência - Escola Teste 01', 'mock:secretaria', 'SCHOOL-01', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-02', 'EMERGENCY', 'Canal de Emergência - Escola Teste 02', 'mock:secretaria', 'SCHOOL-02', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-03', 'EMERGENCY', 'Canal de Emergência - Escola Teste 03', 'mock:secretaria', 'SCHOOL-03', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-04', 'EMERGENCY', 'Canal de Emergência - Escola Teste 04', 'mock:secretaria', 'SCHOOL-04', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-05', 'EMERGENCY', 'Canal de Emergência - Escola Teste 05', 'mock:secretaria', 'SCHOOL-05', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-06', 'EMERGENCY', 'Canal de Emergência - Escola Teste 06', 'mock:secretaria', 'SCHOOL-06', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-07', 'EMERGENCY', 'Canal de Emergência - Escola Teste 07', 'mock:secretaria', 'SCHOOL-07', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-08', 'EMERGENCY', 'Canal de Emergência - Escola Teste 08', 'mock:secretaria', 'SCHOOL-08', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-09', 'EMERGENCY', 'Canal de Emergência - Escola Teste 09', 'mock:secretaria', 'SCHOOL-09', TRUE, 'ACTIVE'),
    ('emergency:SCHOOL-10', 'EMERGENCY', 'Canal de Emergência - Escola Teste 10', 'mock:secretaria', 'SCHOOL-10', TRUE, 'ACTIVE')
ON CONFLICT (id) DO UPDATE
SET
    type = EXCLUDED.type,
    title = EXCLUDED.title,
    created_by = EXCLUDED.created_by,
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
    ('emergency:SCHOOL-01', 'mock:gestor-escola-01', 'MEMBER'),
    ('emergency:SCHOOL-01', 'mock:operador-escola-01', 'MEMBER'),
    ('emergency:SCHOOL-01', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-01', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-02', 'mock:gestor-escola-02', 'MEMBER'),
    ('emergency:SCHOOL-02', 'mock:operador-escola-02', 'MEMBER'),
    ('emergency:SCHOOL-02', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-02', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-03', 'mock:gestor-escola-03', 'MEMBER'),
    ('emergency:SCHOOL-03', 'mock:operador-escola-03', 'MEMBER'),
    ('emergency:SCHOOL-03', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-03', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-04', 'mock:gestor-escola-04', 'MEMBER'),
    ('emergency:SCHOOL-04', 'mock:operador-escola-04', 'MEMBER'),
    ('emergency:SCHOOL-04', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-04', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-05', 'mock:gestor-escola-05', 'MEMBER'),
    ('emergency:SCHOOL-05', 'mock:operador-escola-05', 'MEMBER'),
    ('emergency:SCHOOL-05', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-05', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-06', 'mock:gestor-escola-06', 'MEMBER'),
    ('emergency:SCHOOL-06', 'mock:operador-escola-06', 'MEMBER'),
    ('emergency:SCHOOL-06', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-06', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-07', 'mock:gestor-escola-07', 'MEMBER'),
    ('emergency:SCHOOL-07', 'mock:operador-escola-07', 'MEMBER'),
    ('emergency:SCHOOL-07', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-07', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-08', 'mock:gestor-escola-08', 'MEMBER'),
    ('emergency:SCHOOL-08', 'mock:operador-escola-08', 'MEMBER'),
    ('emergency:SCHOOL-08', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-08', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-09', 'mock:gestor-escola-09', 'MEMBER'),
    ('emergency:SCHOOL-09', 'mock:operador-escola-09', 'MEMBER'),
    ('emergency:SCHOOL-09', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-09', 'mock:guarda', 'MEMBER'),
    ('emergency:SCHOOL-10', 'mock:gestor-escola-10', 'MEMBER'),
    ('emergency:SCHOOL-10', 'mock:operador-escola-10', 'MEMBER'),
    ('emergency:SCHOOL-10', 'mock:secretaria', 'MEMBER'),
    ('emergency:SCHOOL-10', 'mock:guarda', 'MEMBER')
ON CONFLICT (conversation_id, identity_id) DO UPDATE
SET
    member_role = EXCLUDED.member_role,
    left_at = NULL;

COMMIT;
