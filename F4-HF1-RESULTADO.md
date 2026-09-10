# EduVigIA 2.0.0-F4-R1-HF1 — Resultado de preparação

Base: `2.0.0-F4-R1` (F4 aplicada, homologação rejeitada por falso negativo de preflights legados).

## Correções

- Preflights preservados F2/F3/NVR/Central de Alertas deixam de exigir uma string de versão antiga; passam a validar somente seus contratos funcionais.
- `HOMOLOGAR-EDUVIGIA-F4.ps1` adiciona gate `LEGACY_PREFLIGHT_VERSION_AGNOSTIC`.
- Removida prop JSX duplicada `videoDevices={videoDevices}` em `CamerasPage`.
- Versão visual, backend, Compose, package e diagnóstico alinhados em `2.0.0-F4-R1-HF1`.
- Nenhuma migration nova. Alembic permanece em `20260909_205_f4`.
- Nenhuma alteração funcional em playback, evidências, PTZ ou multi-channel.

## Validação local

- Backend: `69 passed`.
- Preflights legados sem acoplamento a versão exata.
- Duplicidade JSX removida.
- Release sem `.env`, chaves privadas, banco local, `node_modules` ou caches.

O build Docker e a homologação runtime permanecem gates obrigatórios no Windows do usuário.
