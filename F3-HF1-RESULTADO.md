# EduVigIA 2.0.0-F3-R1-HF1 — Resultado

Hotfix de ordem de boot da F3 PTZ.

## Causa corrigida
A API F3 era iniciada antes da migration `20260908_203_f3`. O startup consultava a tabela `cameras` já com os campos `ptz_*` do ORM, enquanto o banco ainda estava no schema F2, fazendo a API entrar em restart antes de o instalador alcançar o Alembic.

## Correção
Nova ordem de subida:
1. build API/Web;
2. certificado local;
3. PostgreSQL/Redis/MediaMTX;
4. readiness do PostgreSQL;
5. Alembic upgrade head em runner efêmero;
6. boot da API com schema atualizado;
7. healthcheck da API;
8. restante da stack.

Sem nova migration e sem alteração funcional no PTZ.

## Validação local
- Backend: 56/56 testes aprovados.
- Alembic PostgreSQL offline: aprovado.
- Migration F3 permanece `20260908_203_f3`.
- Contrato de ordem `MIGRATION_BEFORE_API_BOOT_CONTRACT` adicionado.
