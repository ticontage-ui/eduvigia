# EduVigIA 2.0.0-F7-R3 — HF8 Camera Fleet Aggregate Status

> Este HF8 é um hotfix de estabilização da F7-R3. Não é a fase F8/SOS.

## Objetivo

Tornar o indicador global `SISTEMA ...` coerente com o estado agregado real
das câmeras.

## Regra canônica

- todas as câmeras `ONLINE`:
  - `SISTEMA ONLINE`
  - verde (`success`);

- existe mistura entre `ONLINE` e `OFFLINE`:
  - `SISTEMA PARCIAL`
  - laranja (`warning`);

- todas as câmeras `OFFLINE`:
  - `SISTEMA OFFLINE`
  - vermelho (`danger`);

- existe estado intermediário/desconhecido/degradado sem que todas estejam
  offline:
  - `SISTEMA COM ATENÇÃO`
  - laranja (`warning`);

- nenhuma câmera cadastrada:
  - `SEM CÂMERAS`
  - neutro/cinza.

## Escopo visual

A mesma lógica é aplicada:

1. ao selo no cabeçalho das páginas que usam `Page`;
2. ao indicador no topo do Dashboard.

A saúde de NVR/gravadores continua independente e não interfere neste indicador.

## Implementação

- `CameraFleetStatusContext`;
- `deriveCameraFleetStatus(cameras)`;
- cálculo reativo via `useMemo`;
- `Page` passa a consumir o estado agregado;
- `Dashboard` usa a mesma fonte;
- variantes visuais `onlineStatus.success|warning|danger|neutral`.

## Banco/backend

- nenhuma migration;
- nenhum endpoint novo;
- backend inalterado;
- Alembic permanece `20260911_209_f7r3`.

## Base obrigatória

Branch:
`feature/f7-r3-camera-events-health`

HEAD base:
`57c8746e3288521d4bb780f6bc4c9601909b456e`

O runtime HF7 Global Action Feedback deve estar implantado antes do PREP.
