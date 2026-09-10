# EduVigIA 2.0.0-F2-R1-HF3 — F2 VMS Básico

Base de origem: `2.0.0-F1-R1-HF2`.

## Implementado

- cadastro de NVR/DVR preservado com descoberta Hikvision/ISAPI;
- cada câmera passa a ter dois perfis independentes: `MAIN` e `SUB`;
- metadados separados por perfil: codec, resolução, FPS, bitrate e status;
- RTSP customizado aceita URL MAIN e URL SUB independentes;
- canais Hikvision continuam usando MAIN `x01` e SUB `x02`;
- Monitoramento com grades 1/4/9/16;
- modo de qualidade `AUTO`, `SUB` e `MAIN`;
- `AUTO`: MAIN em grade 1/fullscreen e SUB nas grades 4/9/16;
- fullscreen troca automaticamente para MAIN e volta ao SUB ao sair;
- favoritos persistidos no banco por usuário;
- atualização leve de status apenas das câmeras visíveis, em lotes de até 16;
- tentativa automática de reconexão do player;
- resposta da API não expõe URLs RTSP nem paths com credenciais;
- migration `20260908_202_f2`.

## Fora do escopo desta fase

- playback/gravações;
- exportação forense;
- PTZ avançado;
- mapas e plantas;
- SOS/PTT/chat;
- IA.

## Validação local de desenvolvimento

- backend: `49 passed`;
- Alembic offline PostgreSQL: aprovado;
- Python compile: aprovado;
- frontend: build final deve ser validado no Docker/Windows pelo homologador F2.

A F2 somente é considerada homologada após `EDUVIGIA_F2_VMS_BASIC=APPROVED` no ambiente do usuário.
