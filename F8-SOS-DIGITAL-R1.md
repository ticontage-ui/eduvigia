# EduVigIA 2.0.0-F8-R1 — SOS / Pânico e Acionamento de Emergência

## Base
- Source baseline: `2.0.0-F7-R3`
- Base HEAD: `322ab424f8a0ff4dc9eb56c4cb672b8e3fe45b85`
- Target branch: `feature/f8-sos`
- Target version: `2.0.0-F8-R1`
- Alembic: `20260915_210_f8_sos`
- Down revision: `20260911_209_f7r3`

## Contrato funcional

### Perfis escolares
`GESTOR_ESCOLA` e `OPERADOR_ESCOLA`:
- `sos:view`;
- `sos:use`;
- visualizam somente SOS da própria escola;
- podem acionar;
- novo acionamento durante SOS aberto reforça o mesmo evento;
- podem solicitar cancelamento;
- não podem reconhecer nem encerrar.

### Central
`GESTOR_SECRETARIA`, `SUPERVISOR_GUARDA`, `OPERADOR_GUARDA` e
`DESPACHANTE_GUARDA`:
- `sos:view`;
- `sos:operate`;
- reconhecem;
- encerram;
- classificam falso alarme.

`TECNICO` não recebe acesso SOS.

### Acionamento
Primeiro acionamento:
1. cria `sos_events`;
2. cria alerta `CRITICA`, `source=SOS`;
3. cria ocorrência `EMERGENCIA`;
4. cria timeline SOS;
5. cria timeline da ocorrência;
6. cria notificação vinculada à escola;
7. gera auditoria.

Acionamento repetido:
- reutiliza o mesmo SOS aberto;
- não duplica alerta nem ocorrência;
- incrementa `repeat_count`;
- atualiza `last_triggered_at`;
- se havia pedido de cancelamento, retorna a `ACTIVE`.

### Workflow
- `ACTIVE`
- `ACKNOWLEDGED`
- `CANCEL_REQUESTED`
- `RESOLVED`
- `FALSE_ALARM`

A escola não encerra diretamente. Pedido de cancelamento depende da validação
da Central.

## Frontend
- menu `SOS / Emergência`;
- botão SOS permanente no topo para perfil escolar;
- KPIs;
- lista de eventos;
- detalhe e timeline;
- reconhecer, pedir cancelamento, encerrar e falso alarme;
- feedback global para as ações;
- atualização automática silenciosa a cada 5 segundos.

## Segurança
- escopo escolar server-side;
- notificação recebe `school_id` para evitar vazamento entre escolas;
- serialização por advisory lock no PostgreSQL;
- índice único parcial: apenas um SOS operacional aberto por escola;
- auditoria de todas as transições.

## Gate PREP
O PREP:
- não modifica o runtime;
- usa worktree isolado;
- exige branch F8 antiga ser ancestral da base atual;
- roda regressão completa: 100 testes existentes + 7 F8 = 107;
- builda Web;
- clona o banco atual para PostgreSQL temporário;
- aplica a migration F8 somente no clone;
- verifica Alembic/tabelas/índice;
- confirma runtime F7-R3 intacto;
- somente depois commita e faz fast-forward de `feature/f8-sos`.
