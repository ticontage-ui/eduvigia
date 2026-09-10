# EduVigIA 2.0.0-F3-R1-HF6 — F3 PTZ Operacional

Baseline de origem: `2.0.0-F2-R1-HF3`.

## Implementado

- Controle PTZ Hikvision/ISAPI em câmeras diretas e canais de NVR/DVR.
- Pan/tilt em 8 direções, zoom +/− e comando STOP.
- Velocidade operacional de 1 a 7 com normalização para comandos ISAPI.
- `ptz:control` separado de `cameras:write`.
- Isolamento por escola preservado para usuários escolares.
- Lease PTZ por câmera com expiração para impedir disputa entre operadores.
- Supervisor da Guarda e Administrador da Secretaria podem assumir controle com `force` quando necessário.
- Presets 1–256 com nome local, salvar posição, chamar e excluir.
- Auditoria de assumir/liberar controle, movimento, STOP e presets.
- Configuração PTZ no cadastro da câmera: habilitado, protocolo, canal, porta HTTP/HTTPS e HTTPS.
- Canais importados de NVR marcados como PTZ recebem habilitação e canal automaticamente quando `camera_type=PTZ`.
- Interface PTZ no Monitoramento com comandos por pressionar/soltar e STOP explícito.
- Credenciais técnicas continuam excluídas da serialização da API.

## Validação local

- Backend: `56 passed`, `0 failed`.
- F3 preflight: `EDUVIGIA_F3_PTZ_PREFLIGHT_OK`.
- Python compile: PASS.
- JSX parse por TypeScript transpile: PASS.
- Alembic PostgreSQL offline: PASS; head `20260908_203_f3`.
- F2 VMS preservada na mesma árvore.

## Limites desta fase

- O transporte PTZ homologado é **Hikvision ISAPI**.
- ONVIF PTZ não é declarado funcional nesta fase sem equipamento compatível de campo.
- O pacote não executa movimento físico automaticamente durante instalação/homologação.
- O gate de hardware permanece `PENDING_FIELD_TEST` até um PTZ real ser testado com operador presente.

## Gate esperado no Windows/Docker

- `EDUVIGIA_F3_PTZ_CORE=APPROVED`
- `EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST`
- `EDUVIGIA_F3_UPDATE=APPROVED`
- `BASELINE=2.0.0-F3-R1-HF6`
