# Matriz de Homologação — F3 PTZ Operacional

Baseline candidata: `2.0.0-F3-R1-HF6`.

| Gate | Critério |
|---|---|
| VERSION | `VERSION.txt = 2.0.0-F3-R1-HF6` |
| COMPOSE_DEV_CONFIG | Compose DEV válido |
| COMPOSE_PROD_CONFIG | Compose PROD válido |
| RUNTIME_ENDPOINTS | Web/API/Proxy/Prometheus operacionais |
| ALEMBIC_F3_HEAD | `20260908_203_f3` |
| F2_BASE_CONTRACT_PRESERVED | Contrato VMS F2 preservado |
| BACKEND_F3_PTZ_CONTRACT | Rotas, modelos, direções, velocidades e RBAC F3 válidos |
| DATABASE_F3_PTZ_CONTRACT | Colunas PTZ + leases + presets no PostgreSQL |
| PTZ_SECURITY_RBAC_CONTRACT | Credenciais protegidas + `ptz:control` nos perfis autorizados |
| FRONTEND_F3_PTZ_CONTRACT | Painel PTZ, STOP, lease, presets e eventos de pressionar/soltar presentes |
| TEST_RUNNER_APP_IMPORT | Runner isolado importa a aplicação |
| BACKEND_REGRESSION_ISOLATED | Toda a suíte roda em SQLite efêmero |
| TEST_GATE_ISOLATED_FROM_RUNTIME_DB | Testes não apontam para PostgreSQL runtime |
| WEB_BUILD_RUNTIME | Container Web executando após build real |

## Hardware

O gate de software pode ser aprovado sem movimentar equipamento físico. O resultado final da instalação deve registrar:

`EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST`

até que uma câmera PTZ Hikvision real seja testada de forma supervisionada no Monitoramento.
