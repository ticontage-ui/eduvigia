# EduVigIA 2.0.0-F3-R2 — Matriz de homologação

## HT — Técnica

| Gate | Esperado |
|---|---|
| VERSION | PASS |
| COMPOSE_DEV_CONFIG | PASS |
| COMPOSE_PROD_CONFIG | PASS |
| NO_RUNTIME_ENV_FILE | PASS |
| POSTGRES_ENV_ALLOWLIST | PASS |
| API_ENV_ALLOWLIST | PASS |
| RUNTIME_ENDPOINTS | PASS |
| ALEMBIC_F3R2_HEAD | PASS |
| F2_BASE_CONTRACT_PRESERVED | PASS |
| BACKEND_F3_PTZ_CONTRACT | PASS |
| DATABASE_F3_PTZ_CONTRACT | PASS |
| PTZ_SECURITY_RBAC_CONTRACT | PASS |
| FRONTEND_F3_PTZ_CONTRACT | PASS |
| BACKEND_F3R2_MULTICHANNEL_CONTRACT | PASS |
| DATABASE_F3R2_MULTICHANNEL_CONTRACT | PASS |
| MULTICHANNEL_CREDENTIAL_SECURITY | PASS |
| FRONTEND_F3R2_MULTICHANNEL_CONTRACT | PASS |
| BACKEND_REGRESSION_ISOLATED | PASS |
| TEST_GATE_ISOLATED_FROM_RUNTIME_DB | PASS |
| MIGRATION_BEFORE_API_BOOT_CONTRACT | PASS |
| BOOTSTRAP_MINIMAL_DOCKER_RUN | PASS |
| PS51_DOCKER_STDERR_COMPAT | PASS |
| WEB_BUILD_RUNTIME | PASS |

Resultado técnico esperado:

```text
EDUVIGIA_F3_PTZ_CORE=APPROVED
EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST
EDUVIGIA_F3R2_MULTICHANNEL_CORE=APPROVED
EDUVIGIA_F3R2_THERMAL_HARDWARE=PENDING_FIELD_TEST
```

## HF — Funcional

Validar no painel:

1. criar um dispositivo físico `BISPECTRUM` com um único IP;
2. usar `Descobrir canais` e confirmar canais lógicos retornados pelo equipamento;
3. criar/vincular CH1 como `VISIBLE` e CH2 como `THERMAL` de acordo com o equipamento real;
4. confirmar que ambos aparecem no Monitoramento como canais distintos do mesmo dispositivo;
5. validar MAIN/SUB em cada canal;
6. validar agrupamento/ordenação no mosaico;
7. confirmar que nenhuma credencial é exibida nas respostas da API/UI;
8. validar que câmeras F2/F3 existentes continuam operacionais.

## HC — Hardware térmico/bi-spectrum

Obrigatório antes da homologação de campo:

- um único IP físico;
- sensor óptico reproduz vídeo correto;
- sensor térmico reproduz vídeo correto;
- MAIN/SUB por sensor quando o modelo disponibilizar;
- descoberta ISAPI coerente com o firmware/modelo;
- PTZ somente nos canais que efetivamente suportarem o recurso;
- nenhuma duplicação de credencial/dispositivo necessária.

Até esse teste:

```text
EDUVIGIA_F3R2_THERMAL_HARDWARE=PENDING_FIELD_TEST
```
