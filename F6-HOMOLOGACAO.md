# Matriz de Homologação — EduVigIA F6

## HT — Técnico

Esperado:

```text
PASS|VERSION
PASS|COMPOSE_DEV_CONFIG
PASS|COMPOSE_PROD_CONFIG
PASS|RUNTIME_ENDPOINTS
PASS|DATABASE_F6_MAP_COORDINATE_CONTRACT
PASS|ALEMBIC_F6_SCHEMA_BASE
PASS|BACKEND_F6_OPERATIONAL_MAPS_CONTRACT
PASS|F6_MAP_RBAC_SCOPE_CONTRACT
PASS|FRONTEND_F6_OPERATIONAL_MAP_CONTRACT
PASS|F6_ONPREM_TILE_CONFIG_CONTRACT
PASS|BACKEND_REGRESSION_ISOLATED
PASS|TEST_GATE_ISOLATED_FROM_RUNTIME_DB
PASS|WEB_BUILD_RUNTIME
EDUVIGIA_F6_OPERATIONAL_MAPS_CORE=APPROVED
```

## HF — Funcional

Validar no navegador:

1. abrir `Mapa Operacional`;
2. confirmar que escolas com latitude/longitude aparecem como marcadores;
3. testar filtros Normal/Atenção/Crítica e busca;
4. selecionar uma escola e conferir os totais de câmeras/alertas/ocorrências;
5. abrir Monitoramento a partir do painel lateral;
6. confirmar que escola sem coordenada aparece na lista de saneamento;
7. em perfil de Escola, confirmar que apenas a unidade vinculada aparece.

## HC — Campo

Antes de rollout municipal, preencher coordenadas reais das escolas e validar posicionamento visual. Até isso ocorrer:

```text
EDUVIGIA_F6_MAP_DATA=PENDING_FIELD_COORDINATES
```

## Tiles on-prem

Em ambiente sem Internet, configurar `EDUVIGIA_MAP_TILE_URL` para um servidor de tiles interno compatível com `{z}/{x}/{y}`. O mapa mantém grid de fallback caso os tiles não estejam disponíveis.
