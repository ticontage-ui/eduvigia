# EduVigIA 2.0.0-F4-R1-HF1 — Playback + Evidências Forenses

Base: `2.0.0-F3-R2`.

## Escopo
- Playback por canal lógico (NVR/DVR, câmera/dispositivo Hikvision com gravação local compatível).
- Busca de timeline via ISAPI ContentMgmt.
- URL RTSP de playback construída apenas no backend; credenciais nunca serializadas.
- Preview temporário privado de até 120 s.
- Exportação forense MP4 de até 30 min por operação.
- Evidência pode ser vinculada a ocorrência, mas não é obrigatório.
- Metadados preservam escola, dispositivo, canal lógico, sensor, origem e janela temporal.
- SHA-256 no ato da criação.
- Verificação posterior de integridade e detecção de alteração/arquivo ausente.
- Cadeia de custódia para criação, verificação e download.
- RBAC: playback para Secretaria/Guarda/Escola/Técnico conforme escopo; exportação forense restrita a perfis operacionais autorizados.

## Migration
`20260909_205_f4` <- `20260909_204_f3r2`.

## Validação local
- Backend: 69/69 testes PASS.
- Python compile: PASS.
- Frontend: build Docker real é gate obrigatório no ambiente Windows.
- Hardware Hikvision: PENDING_FIELD_TEST.
