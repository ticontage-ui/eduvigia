# EduVigIA 1.8.8-R1 — Fase 5

## Integração de IA: contrato, servidores, regras, eventos e telemetria

### Entregas

- novo módulo **Integração IA** no frontend;
- cadastro, edição, teste e desativação segura de servidores de IA;
- tokens técnicos criptografados com a chave de credenciais do EduVigIA;
- contrato de integração `2026-07-08.v1`;
- regras por servidor, escola e câmera;
- eventos autenticados, auditáveis e deduplicados;
- telemetria operacional de CPU, memória, GPU, fila e FPS;
- escopo escolar aplicado à consulta de eventos;
- endpoints internos para integração externa;
- preflight específico da Fase 5.

### Limite de escopo

Esta versão não executa modelos, não processa imagens e não substitui um servidor de inferência. Ela prepara a camada de contrato, segurança, administração e observabilidade necessária para a próxima fase.

### Compatibilidade

- origem suportada: `1.8.7-R1`;
- destino: `1.8.8-R1`;
- PostgreSQL e Redis preservados;
- MediaMTX, Nginx e Prometheus preservados;
- backup, restauração isolada e rollback preservados.
