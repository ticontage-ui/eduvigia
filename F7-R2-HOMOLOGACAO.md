# EduVigIA 2.0.0-F7-R2 — Homologação

Status inicial: **CANDIDATA / NÃO HOMOLOGADA**

Objetivo: estabilizar a baseline F7 antes da F8 SOS Digital, sem misturar correções de base com a nova funcionalidade de emergência.

## Escopo obrigatório

### Escolas
- editar escola existente;
- impedir código de escola duplicado na edição;
- `KIT_01` a `KIT_16`, correspondendo de 4 a 64 câmeras em incrementos de 4;
- ativar/inativar escola gera notificação operacional no sino.

### Câmeras
- código automático persistente `CAM-000001`;
- código não é digitado pelo operador;
- backfill de códigos nas câmeras existentes;
- pesquisa por código;
- teste/importação em lote até 64 canais/câmeras.

### Notificações
- leitura por usuário, sem compartilhar `read_at` global entre usuários;
- escopo escolar para eventos de uma escola;
- contador de não lidas correto;
- marcar uma e marcar todas como lidas;
- clique navega para o módulo associado.

### Alertas
- criação manual para perfis com `alerts:operate`;
- workflow, atribuição, evidência, ocorrência e histórico preservados;
- remover da UI/API pública campos de confiança de IA e o filtro/coluna de origem associado ao escopo antigo;
- manter `source` apenas como metadado interno de integração, necessário para futuras origens como SOS;
- alerta convertido em ocorrência usa categoria `SEGURANCA`, sem resíduo `BEM_ESTAR`.

### Concorrência
- protocolo de ocorrência deixa de usar `count()+1`;
- PostgreSQL usa contador anual transacional em `occurrence_sequences`.

## Migration

Head esperado:

```text
20260911_208_f7r2
```

Down revision:

```text
20260910_207_f7
```

A migration cria/ajusta:
- `cameras.code` + índice único;
- `notifications.school_id`;
- `notification_reads`;
- `occurrence_sequences`.

## Regra de implantação

1. manter runtime F7-R1 funcionando;
2. preparar candidata em worktree/branch isolada;
3. backup PostgreSQL validado;
4. build API e Web isolados;
5. suíte backend completa;
6. migration testada sobre cópia restaurada do PostgreSQL;
7. somente depois criar commit/push da candidata;
8. runtime real só será atualizado em etapa separada de promoção;
9. migration real deve ocorrer com API/Web parados e antes de subir F7-R2.

## Gates

- [ ] baseline/HEAD conferidos;
- [ ] backup validado;
- [ ] `docker compose config` DEV/PROD;
- [ ] API build;
- [ ] Web build;
- [ ] backend regression;
- [ ] testes F7-R2;
- [ ] Alembic head;
- [ ] restore isolado do dump;
- [ ] migration F7 -> F7-R2 em clone do banco;
- [ ] downgrade/upgrade test no clone;
- [ ] Git diff check;
- [ ] secrets hygiene;
- [ ] Browser QA;
- [ ] health/readiness após promoção;
- [ ] regressão F0-F7 após promoção.

Somente após todos os gates:

```text
EDUVIGIA_F7_R2=APPROVED
```
