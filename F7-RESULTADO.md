# EduVigIA 2.0.0-F7-R1 — Resultado de preparação

Status: **CANDIDATA PARA HOMOLOGAÇÃO**

Baseline de origem: `2.0.0-F6-R1`.

## Entregas
- Plantas baixas por escola, prédio/bloco e pavimento.
- Upload autenticado JPG/PNG/WebP, máximo 15 MB, com validação de assinatura do arquivo.
- Persistência em `data/floorplans`.
- Posicionamento de câmeras/canais por coordenadas percentuais e rotação.
- Suporte a canais multi-sensor VISÍVEL/TÉRMICO da F3-R2.
- RBAC `floorplans:view` e `floorplans:write` com escopo escolar.
- Auditoria de cadastro, posicionamento e exclusão.
- Integração no menu e acesso a partir do Mapa Operacional.

## Banco
Migration: `20260910_207_f7` → down revision `20260910_206_f5`.
Tabelas: `floor_plans`, `floor_plan_cameras`.

## Validações locais
- Backend: **86/86 testes PASS**.
- Testes F7: **6/6 PASS**.
- Python compile: PASS.
- JSX TypeScript parse: PASS.
- Alembic PostgreSQL offline: PASS.
- Build Docker/Web permanece gate obrigatório no Windows do usuário.

A F7 somente será considerada homologada após `EDUVIGIA_F7_FLOOR_PLANS_CORE=APPROVED` no ambiente do usuário.
