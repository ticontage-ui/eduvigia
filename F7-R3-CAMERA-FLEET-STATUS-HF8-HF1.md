# EduVigIA 2.0.0-F7-R3 — HF8-HF1 Fleet Feedback Tone

## Motivo

No Browser QA do HF8, o selo `SISTEMA PARCIAL` ficou corretamente laranja,
porém a faixa global exibida após `Atualizar saúde` continuou verde mesmo com
4 câmeras online e 1 offline.

A operação HTTP havia sido concluída com sucesso, mas o feedback visual precisa
representar o estado operacional resultante da frota.

## Regra aplicada ao feedback de Atualizar saúde

- todas as câmeras online:
  - faixa verde;
  - título `Saúde das câmeras atualizada`;

- mistura online + offline:
  - faixa laranja;
  - título `Sistema de câmeras parcial`;

- todas as câmeras offline:
  - faixa vermelha;
  - título `Sistema de câmeras offline`;

- degradadas/desconhecidas sem todas offline:
  - faixa laranja;
  - título `Sistema de câmeras com atenção`.

A faixa laranja permanece até 8 segundos e pode ser fechada manualmente.

## Importante

O HF8-HF1 não altera:
- regra do selo `SISTEMA ONLINE/PARCIAL/OFFLINE`;
- API;
- banco;
- Alembic;
- NVR/gravadores.

## Base obrigatória

Branch:
`feature/f7-r3-camera-events-health`

HEAD:
`8f0cdc248ba82a5fd5b8c39b216a557d6deb7fc9`

Runtime esperado:
`eduvigia-f7r3-camera-fleet-status-hf8-web:20260915-162544`
