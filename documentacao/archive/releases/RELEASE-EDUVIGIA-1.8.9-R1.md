# EduVigIA 1.8.9-R1

## Fase 6 — Motor de Inferência de IA e Pipeline de Vídeo

Esta versão adiciona o primeiro motor local de visão computacional do EduVigIA. O serviço analisa streams RTSP de câmeras habilitadas para IA, aplica regras configuradas na Fase 5, registra telemetria e envia eventos autenticados para a API.

### Motor inicial

- detector: `motion`;
- modelo lógico: `eduvigia-motion-v1`;
- versão do modelo: `1.0.0`;
- execução em CPU por padrão;
- GPU NVIDIA detectada automaticamente quando disponível;
- captura via FFmpeg com RTSP/TCP;
- stream SUB por padrão e MAIN opcional por regra.

### Segurança e privacidade

- token técnico exclusivo gerado pelo instalador;
- acesso temporário ao stream limitado à câmera e ao perfil da regra;
- evidências locais sem envio a serviços externos;
- sem reconhecimento facial;
- sem biometria;
- sem análise emocional.

### Observabilidade

- health e readiness do motor;
- métricas Prometheus;
- telemetria de CPU, memória, GPU, fila, FPS, eventos e falhas de captura;
- alerta Prometheus quando o motor não é coletado.

### Limites desta versão

O detector inicial identifica movimento/alteração de cena. Modelos ONNX específicos para pessoa, aglomeração, objeto abandonado e outras classes deverão ser homologados em atualização posterior, com dataset, métricas de precisão e validação de campo.


## Revisão R2

- Corrige conflito `UNIQUE constraint failed: ai_servers.name` nos testes executados com `EDUVIGIA_AI_ENGINE_TOKEN` configurado.
- O helper de teste passa a reutilizar o motor registrado no startup.
- O cadastro automático do motor escolhe um nome alternativo seguro quando já existe outro servidor com o nome institucional.
- A limpeza do preflight não tenta remover volumes que não chegaram a ser criados.
- Total validado: 51 testes automatizados.


## Revisão R3 — continuidade do ambiente ticon

- Preserva os blocos `ports` dos serviços já instalados antes de aplicar o Compose da Fase 6.
- Mantém o proxy HTTPS homologado em `18443` neste computador.
- Mantém WebRTC/ICE em `18189:18189/udp` quando essa é a configuração ativa.
- Preserva `webrtcAdditionalHosts`, incluindo `192.168.1.100`, sem substituir pelo endereço público da interface de Internet.
- Detecta dinamicamente as portas efetivas para validação e apresentação dos endereços finais.
- Mantém `.env`, PostgreSQL, Redis, Prometheus, câmeras, credenciais, evidências e certificados.
- Continua exigindo preflight isolado antes da instalação definitiva.
