# Checklist — Fase 7: Central de Alertas, Evidências e Despacho

Versão: **EduVigIA 1.9.0-R1**

## Backend

- [x] Eventos do motor de IA geram alertas operacionais automaticamente.
- [x] Deduplicação do evento também impede alertas duplicados.
- [x] Workflow: `NOVO`, `EM_ATENDIMENTO`, `CONFIRMADO`, `DESCARTADO`, `ENCERRADO`.
- [x] Responsável operacional pode ser atribuído ao alerta.
- [x] Histórico imutável de criação, atribuição, status e abertura de ocorrência.
- [x] Evidência JPEG entregue por endpoint autenticado.
- [x] Validação de caminho impede leitura fora da pasta de dados.
- [x] Isolamento por escola aplicado à lista, resumo, detalhes e evidência.
- [x] Conversão do alerta em ocorrência preserva resumo e referência da evidência.
- [x] Auditoria e notificações para ações operacionais.

## Interface

- [x] Central de Alertas com atualização automática.
- [x] KPIs de novos, em atendimento, críticos, evidências e últimas 24 horas.
- [x] Filtros por texto, status, prioridade e origem.
- [x] Detalhes com evidência e vídeo ao vivo protegido.
- [x] Histórico cronológico do atendimento.
- [x] Atribuição de responsável.
- [x] Ações de assumir, confirmar, descartar, encerrar e abrir ocorrência.
- [x] Aviso sonoro opcional para novos alertas.

## Observabilidade e segurança

- [x] Métricas `eduvigia_alerts_active`, `eduvigia_alerts_new` e `eduvigia_alerts_critical`.
- [x] Regras Prometheus para alerta crítico pendente e acúmulo de fila.
- [x] Reconhecimento facial, biometria e análise emocional permanecem desativados.
- [x] Evidências permanecem locais e não são enviadas para nuvem.
