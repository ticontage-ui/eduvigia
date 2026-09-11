# EduVigIA F7-R3 — Health Inventory HF5

Corrige a inconsistência observada após a F7-R3:

- câmeras cadastradas podem existir sem linha persistente em `camera_health`;
- o endpoint `/camera-health` consegue sintetizar uma resposta, mas os KPIs que
  consultam diretamente `camera_health` podem ficar incompletos;
- o problema ocorre principalmente quando câmeras/canais são cadastrados ou
  importados depois da migration `20260911_209_f7r3`.

## Correção permanente

- reconciliação idempotente no startup;
- criação de `camera_health` no cadastro de câmera;
- criação de `camera_health` na importação de canais do NVR/DVR;
- criação de `camera_health` em canais multisensor;
- criação de `recorder_health` no cadastro de gravador;
- preservação de estados derivados de eventos já existentes;
- atualização apenas do vínculo de escola quando necessário.

## Banco

Sem nova migration. O schema permanece `20260911_209_f7r3`.
A correção cria apenas linhas faltantes nas tabelas já existentes.
