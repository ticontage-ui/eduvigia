# EduVigIA 2.0.0-F7-R3 — Camera Events & Health

## Objetivo

Transformar eventos e telemetria provenientes de câmeras e gravadores em eventos
operacionais normalizados no EduVigIA, com saúde do dispositivo, alertas,
notificações, deduplicação e auditoria.

Esta fase sucede a F7-R2. A preparação da candidata pode ocorrer enquanto a F7-R2
está em Browser QA, mas a F7-R3 **não pode ser promovida ao runtime** antes da
homologação formal da F7-R2.

## Escopo implementado

### Modelo de eventos
- `camera_events`: catálogo operacional normalizado.
- `camera_health`: saúde consolidada por câmera.
- `recorder_health`: saúde consolidada por NVR/DVR.
- correlação por dispositivo/canal/tipo.
- deduplicação de evento ativo com `repeat_count`.
- deduplicação por `event_uid` quando fornecido pelo fabricante.
- `pg_advisory_xact_lock` no PostgreSQL para serializar a correlação.

### Catálogo normalizado
- CAMERA_OFFLINE / CAMERA_ONLINE
- VIDEO_LOSS / VIDEO_RESTORED
- RTSP_FAILURE / RTSP_RESTORED
- MOTION
- TAMPER
- LINE_CROSSING
- INTRUSION
- REGION_ENTRANCE / REGION_EXIT
- OBJECT_LEFT / OBJECT_REMOVED
- PEOPLE_COUNTING
- OCCUPANCY
- QUEUE
- AUDIO_ALARM
- DIGITAL_INPUT
- RECORDING_FAILURE / RECORDING_RESTORED
- STORAGE_FAILURE / STORAGE_WARNING
- NTP_DRIFT
- PTZ_FAULT
- RECORDER_OFFLINE / RECORDER_ONLINE
- DEVICE_REBOOT
- UNKNOWN_DEVICE_EVENT

### Integrações
- normalização de aliases Hikvision ISAPI.
- normalização por tópico ONVIF.
- endpoint genérico de ingestão protegido por `X-EduVigIA-Event-Key`.
- endpoint Hikvision para XML/JSON/multipart.
- captura do primeiro JPEG recebido junto ao evento como evidência.
- endpoint de referência de integração por gravador.
- transições geradas pelos testes/health já existentes de câmera, RTSP e gravador.

### Alertas e notificações
- evento relevante pode gerar alerta operacional automaticamente.
- origem operacional interna: `DISPOSITIVO`, sem reintroduzir origem/confiança de IA.
- notificação vinculada à escola.
- eventos repetidos atualizam o mesmo evento ativo em vez de criar alertas em massa.
- recuperações técnicas fecham automaticamente apenas falhas técnicas recuperáveis.
- eventos de segurança permanecem para triagem do operador.

### Segurança de schema
Antes de `Base.metadata.create_all()` em PostgreSQL, o startup verifica
`alembic_version`. Código F7-R3 não deve iniciar sobre schema F7-R2.

## Migration

- revision: `20260911_209_f7r3`
- down_revision: `20260911_208_f7r2`

Cria:
- `camera_events`
- `camera_health`
- `recorder_health`

Também faz backfill inicial da saúde de câmeras e gravadores existentes.

## Interface

Novo menu **Eventos & Saúde**:
- KPIs de eventos/saúde;
- filtros por escola, câmera, tipo e severidade;
- eventos ativos e repetição;
- saúde RTSP/Main/Sub;
- gravação e armazenamento;
- codec/resolução/FPS/bitrate/NTP;
- saúde de gravadores;
- simulação controlada para QA.

## RBAC

- `events:view`: perfis institucionais/operacionais, escola e técnico conforme escopo.
- `events:operate`: perfis centrais/guarda/técnico.
- usuários de escola permanecem restritos à própria escola.

## O que NÃO deve ser declarado homologado sem hardware

A fase implementa o software core e os receivers/adapters. A homologação completa
com equipamentos reais exige vincular e testar cada mecanismo disponível no
hardware/NVR instalado.

Especialmente:
- Hikvision `ISAPI/Event/notification/alertStream`;
- configuração de HTTP notification/listening server quando aplicável;
- ONVIF Event Service / PullPoint quando suportado;
- eventos analíticos dependentes do modelo/licença da câmera;
- HDD/SD/recording health dependente do equipamento.

Portanto, o gate de software e o gate de hardware são separados.

## Gates de homologação

### Automáticos
- build API;
- build Web;
- suíte backend;
- migration F7-R2 -> F7-R3 em clone PostgreSQL;
- downgrade F7-R3 -> F7-R2;
- re-upgrade F7-R2 -> F7-R3;
- schema/indexes/backfill;
- runtime F7-R2 intacto durante preparação.

### Runtime
- migration-before-boot;
- API health/readiness;
- Web/proxy;
- Event & Health API;
- RBAC e isolamento por escola;
- alerta/notificação/deduplicação;
- evidência.

### Hardware
Para cada equipamento/capacidade suportada:
- gerar evento físico real;
- confirmar recepção;
- confirmar normalização;
- confirmar câmera/canal/escola;
- confirmar alerta/notificação;
- confirmar evidência quando disponível;
- confirmar recuperação;
- confirmar deduplicação;
- confirmar saúde.
