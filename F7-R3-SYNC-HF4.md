# EduVigIA F7-R3 — Sync HF4

Sincronização da candidata `2.0.0-F7-R3 — Camera Events & Health` com os
hotfixes homologados na F7-R2.

## Base F7-R2 homologada para continuidade

- branch: `feature/f7-r2-stabilization`
- head: `63db59049a0f307b929330610d13973bbd51d047`

## Base F7-R3

- branch: `feature/f7-r3-camera-events-health`
- head anterior: `b162e556e64633d6c4609af2d40d3b607d2f6518`

## Sincronizações

- preserva `Eventos & Saúde`;
- preserva `camera_events`, `camera_health` e `recorder_health`;
- preserva Alembic `20260911_209_f7r3`;
- corrige `Modal is not defined` usando `DetailModal`;
- mantém descoberta Hikvision/ISAPI funcional;
- mantém `Fale com o suporte` funcional;
- incorpora layout automático do Monitoramento;
- layouts manuais 1/4/6/9/16/25/36;
- 5 câmeras no automático = grade 3 x 2;
- preferência de layout persistida localmente por usuário;
- aumento discreto da logomarca oficial no menu lateral.

## Logo

A marca oficial não é redesenhada. O mesmo asset `/eduvigia-brand.png` é
preservado, apenas com dimensões ligeiramente maiores no menu lateral.

## Escopo técnico

Frontend apenas nesta sincronização. O backend da F7-R3 não é alterado.

Mesmo assim, a preparação reexecuta:
- build API;
- 98 testes backend;
- build Web;
- migration F7-R2 -> F7-R3 -> F7-R2 -> F7-R3 em PostgreSQL temporário;
- validação do runtime F7-R2 inalterado.

A promoção da F7-R3 para runtime permanece como etapa separada.
