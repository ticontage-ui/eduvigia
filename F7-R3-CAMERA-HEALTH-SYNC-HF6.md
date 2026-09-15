# EduVigIA 2.0.0-F7-R3 — Camera Health Sync HF6

Fecha a inconsistência encontrada no Browser QA de Eventos & Saúde.

## Problema observado

O Monitoramento conseguia alcançar/exibir câmeras, porém a tela Eventos & Saúde
podia manter `CameraHealth` defasado, por exemplo:

- RTSP = OK;
- MAIN/SUB = FALHA (estado antigo);
- Saúde = OFFLINE.

O motivo era a existência de dois estados que não eram atualizados por todos os
mesmos fluxos: `Camera` e `CameraHealth`.

## Correção

- helper único `sync_camera_health_from_camera`;
- `test_camera_profiles` passa a sincronizar `CameraHealth`;
- teste individual e em lote preservados;
- `monitoring/status-refresh` sincroniza conectividade sem sobrescrever perfis;
- alteração manual de status sincroniza o health correspondente;
- novo `POST /camera-health/refresh`, máximo 16 câmeras por execução;
- refresh explícito testa MAIN/SUB sem provisionar e sem criar eventos/alertas;
- câmera com RTSP acessível e perfil degradado passa a `DEGRADADO`, não `OFFLINE`;
- tabela Eventos & Saúde recebe grid/header correto e espaçamento legível;
- botão “Atualizar saúde” na interface para perfis reais;
- nenhuma migration;
- Alembic permanece `20260911_209_f7r3`.

## Regra operacional

O refresh de saúde é uma verificação técnica sob demanda. Ele atualiza telemetria
e estado, mas retorna `events_generated=0`. O motor de eventos continua separado
para evitar alertas falsos durante uma atualização manual de saúde.
