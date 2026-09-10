# Checklist — Fase 6: Motor de Inferência e Pipeline de Vídeo

- [x] Serviço `ai_engine` independente em container
- [x] API de health, readiness, capabilities, metrics, reload e self-test
- [x] Detector local inicial `eduvigia-motion-v1`
- [x] Processamento padrão do stream SUB e suporte opcional ao MAIN
- [x] Captura de quadros com FFmpeg por RTSP/TCP
- [x] Confiança, limiar de movimento, cooldown e deduplicação
- [x] Evidência JPEG local em `data/ai-evidence`
- [x] Envio autenticado de eventos e telemetria para a API
- [x] Token de vídeo interno, temporário e restrito ao motor local
- [x] Cadastro automático do motor local na tabela `ai_servers`
- [x] Métricas Prometheus e alerta de indisponibilidade
- [x] Operação em CPU e detecção opcional de GPU NVIDIA
- [x] Reconhecimento facial, biometria e análise emocional desabilitados
- [x] Autoteste sintético `ENGINE_PHASE6_SELFTEST_OK`
- [x] Preflight `AI_ENGINE_PHASE6_PREFLIGHT_OK`
- [x] 51 testes automatizados

- [x] Registro local idempotente mesmo quando o startup já cadastrou o motor.
- [x] Colisão de nome em `ai_servers` tratada sem violar a restrição UNIQUE.
- [x] Limpeza de volumes temporários tolerante a volumes inexistentes.

- [x] Portas publicadas do ambiente ativo preservadas estruturalmente na atualização R3.
- [x] HTTPS homologado e WebRTC/ICE `18189:18189/udp` preservados.
- [x] Hosts WebRTC, `.env`, banco, volumes, câmeras e certificados mantidos.
