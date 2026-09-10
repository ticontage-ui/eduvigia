# EduVigIA 1.9.0-R1

## Fase 7 — Central de Alertas, Evidências e Despacho Operacional

Esta versão conecta o motor local de IA à operação humana. Cada evento válido de inferência passa a gerar automaticamente um alerta rastreável, com prioridade, confiança, escola, câmera, evidência protegida e histórico de atendimento.

### Principais entregas

- geração automática de alerta a partir de evento de IA;
- deduplicação por evento externo;
- central em tempo real com filtros e indicadores;
- evidência JPEG autenticada;
- vídeo ao vivo da câmera dentro do detalhe do alerta;
- atribuição de responsável;
- workflow operacional completo;
- histórico de ações;
- abertura de ocorrência a partir do alerta;
- isolamento por escola;
- auditoria e notificações;
- métricas e regras Prometheus.

### Privacidade

A versão não inclui reconhecimento facial, biometria, identificação de alunos, análise emocional ou envio de vídeo para serviços externos.

### Compatibilidade

- versão de origem obrigatória: `1.8.9-R1`;
- preserva `.env`, banco PostgreSQL, Redis, volumes, evidências, certificados e configuração de vídeo;
- preserva os mapeamentos de portas homologados no ambiente ativo;
- mantém o motor `eduvigia-motion-v1` e o container `ai_engine`.
