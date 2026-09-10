# EduVigIA 2.0.0-F3-R2 — Resultado de preparação

Status: **CANDIDATA PARA HOMOLOGAÇÃO**. Esta fase ainda não está homologada no Windows/Docker de destino.

## Objetivo

Implementar a fundação multi-channel/multi-sensor necessária para equipamentos que possuem um único IP físico e múltiplos canais de vídeo, como câmeras térmicas bi-spectrum com sensor óptico e sensor térmico.

## Arquitetura entregue

- `VideoDevice`: equipamento físico, com escola, IP, portas, fabricante/modelo e credenciais únicas.
- `Camera`: canal/sensor lógico associado ao equipamento físico por `device_id`.
- canais lógicos `1..32` por dispositivo;
- tipos de sensor `VISIBLE`, `THERMAL`, `FUSION`, `GENERIC`;
- MAIN/SUB independentes por canal lógico;
- Hikvision RTSP derivado por canal: CH1 `101/102`, CH2 `201/202`, etc.;
- descoberta ISAPI `/ISAPI/Streaming/channels` com normalização dos stream IDs;
- credenciais compartilhadas no dispositivo físico, sem duplicação obrigatória em cada canal;
- integração com PTZ F3 usando credenciais do dispositivo físico quando aplicável;
- UI para cadastrar dispositivo físico, descobrir canais e vincular/criar sensores lógicos;
- Monitoramento identifica sensor/canal e agrupa canais do mesmo dispositivo.

## Migration

- nova revision: `20260909_204_f3r2`
- down revision: `20260908_203_f3`
- cria `video_devices`;
- adiciona em `cameras`: `device_id`, `logical_channel`, `sensor_type`, `sensor_label`, `primary_sensor`;
- converte câmeras IP diretas existentes para a abstração de dispositivo físico preservando dados e streams.

## Validações locais

- Python compile: PASS
- Compose DEV YAML: PASS
- Compose PROD YAML: PASS
- Alembic PostgreSQL offline até `20260909_204_f3r2`: PASS
- F2 + F3 + F3-R2: **19/19 PASS**
- regressão legada: **43/43 PASS**
- total backend: **62/62 PASS**

O build Vite local não foi declarado como aprovado porque a instalação de dependências não concluiu no ambiente de preparação. O instalador mantém o build Docker real de API/Web como gate obrigatório no computador de destino.

## Campo

A detecção/visualização real dos dois sensores de uma câmera térmica bi-spectrum permanece `PENDING_FIELD_TEST` até execução com hardware real.
