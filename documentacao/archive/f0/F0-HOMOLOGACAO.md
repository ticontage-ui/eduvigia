# EduVigIA 2.0 — F0 Clear / Limpeza e Estabilização

Baseline: `2.0.0-F0-R1`

## Estado da entrega

- `EDUVIGIA_F0_CLEAR_STATIC=APPROVED`
- `EDUVIGIA_F0_CLEAR_BACKEND_TESTS=APPROVED`
- `EDUVIGIA_F0_CLEAR_RUNTIME=PENDING`

O gate final `EDUVIGIA_F0_CLEAR=APPROVED` somente deve ser emitido após executar `scripts/HOMOLOGAR-EDUVIGIA-F0.ps1` no ambiente Windows/Docker de homologação.

## Critérios implementados

- IA/Bem-Estar/Reconhecimento Facial removidos do runtime;
- `ai_engine` removido do Compose;
- domínio legado removido do backend/frontend;
- migration `20260908_200_f0_clear` criada;
- `.env`, chave TLS e evidências legadas fora do release;
- HTTP redirecionando para HTTPS, preservando `/healthz`;
- handshake HLS/WebRTC configurado com TLS no MediaMTX;
- porta WebRTC UDP de produção coerente em `18189:18189/udp`;
- Central de Alertas preservada sem dependência de IA;
- script de subida atualizado para aplicar a migration F0 de forma controlada;
- script dedicado de homologação F0 incluído.

## Validação executada nesta entrega

- Backend: `36 passed`, `0 failed`;
- Alembic: geração SQL da cadeia até `20260908_200_f0` aprovada;
- Python: compile/compileall aprovado;
- Frontend: parsing JSX aprovado;
- Compose: YAML de desenvolvimento e produção válido;
- Contrato backend: sem rotas `/ai/*`, sem tabelas `ai_*`, sem `Camera.ai_enabled`, sem `Alert.ai_event_id`;
- busca no runtime: sem referências ativas a IA/Bem-Estar/Reconhecimento Facial;
- release: sem `.env` real e sem chave privada TLS.

## Validações que exigem o ambiente Windows/Docker

- `docker compose build api web` (inclui build Vite limpo);
- subida completa da stack;
- execução real da migration no PostgreSQL da instalação;
- HTTPS/MediaMTX/WebRTC em runtime;
- teste MAIN/SUB com câmera/NVR;
- backup e restore em Docker;
- execução do `scripts/HOMOLOGAR-EDUVIGIA-F0.ps1`.

## Gate final

Quando todos os testes runtime passarem:

`EDUVIGIA_F0_CLEAR=APPROVED`
