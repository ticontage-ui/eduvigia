# Resultado — EduVigIA 2.0.0-F0-R1

## Clear realizado

A baseline `1.9.0-R1` foi convertida para `2.0.0-F0-R1`, preservando o núcleo de segurança escolar e removendo do runtime o escopo descontinuado.

### Removido

- motor/servidor de IA;
- regras, eventos, telemetria e evidências de IA;
- detector de movimento apresentado como IA;
- Bem-Estar;
- reconhecimento facial, biometria e análise de emoções;
- GPU/nvidia-smi e configurações exclusivas da IA;
- campos `cameras.ai_enabled` e `alerts.ai_event_id`;
- serviços, testes e configurações exclusivas do domínio antigo.

### Preservado

- autenticação, sessões e RBAC;
- escolas e usuários;
- câmeras e NVRs;
- Hikvision/ISAPI, RTSP, MAIN/SUB;
- MediaMTX e autorização de streams;
- alertas genéricos;
- ocorrências e despacho existente;
- evidências, equipamentos, manutenção e auditoria;
- PostgreSQL, Redis, Nginx e Prometheus.

### Correções F0

- `.env` real e chave privada TLS retirados do release;
- `.env.example` sem secrets reais;
- HTTP redireciona para HTTPS;
- MediaMTX HLS/WebRTC configurado para TLS;
- porta WebRTC UDP de produção corrigida para `18189:18189/udp`;
- IP ICE fixo removido da configuração e substituído por variável de ambiente;
- migration F0 adicionada para remover estruturas antigas do banco;
- `SUBIR-EDUVIGIA.ps1` atualizado para aplicar migration de forma controlada;
- `HOMOLOGAR-EDUVIGIA-F0.ps1` adicionado.

## Testes executados

`36 passed, 0 failed` no backend.

Também passaram: compile Python, SQL offline do Alembic, parsing JSX, YAML dos Compose e verificações estruturais do contrato F0.

## Pendente de homologação runtime

O ambiente desta auditoria não possui Docker operacional e o registry npm não ficou disponível para um rebuild Vite independente. Portanto a entrega está tecnicamente preparada, mas o gate final depende da execução do validador F0 no ambiente Windows/Docker.
