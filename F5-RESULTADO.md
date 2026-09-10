# EduVigIA 2.0.0-F5-R1 — Resultado de preparação

Fase: F5 — Video Wall Operacional
Baseline de origem: `2.0.0-F4-R1-HF1`
Candidata: `2.0.0-F5-R1`
Migration: `20260910_206_f5`

## Escopo implementado
- Video Wall persistente por operador autorizado.
- Grades 1, 4, 9 e 16 slots.
- Layouts nomeados, edição, exclusão e definição de layout padrão.
- Cada slot referencia um canal lógico de câmera; sensores VISÍVEL/TÉRMICO da F3-R2 podem ocupar slots independentes.
- Qualidade AUTO/SUB/MAIN; AUTO usa MAIN em grade 1 e SUB em grades múltiplas.
- Tela cheia do wall sem alterar os layouts do Monitoramento normal.
- Filtro por escola na configuração dos slots.
- Bloqueio de câmera duplicada no mesmo layout.
- Isolamento dos layouts por usuário.
- RBAC `wall:view` / `wall:write` para operação central; perfis de escola não recebem Video Wall nesta fase.
- Auditoria de criação, alteração, exclusão e definição de padrão.

## Banco
Novas tabelas:
- `video_wall_layouts`
- `video_wall_slots`

## Validação local
- Backend: `75 passed`.
- Python compile: PASS.
- Preflight F5: PASS.
- JSX parse: PASS.
- Alembic PostgreSQL offline: PASS.
- Build frontend local: não homologado neste ambiente; build Docker real permanece gate obrigatório no Windows.

A fase somente deve ser considerada homologada após execução dos gates Windows/Docker.
