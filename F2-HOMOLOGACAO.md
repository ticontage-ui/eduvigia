# Homologação — F2 VMS Básico

Baseline candidata: `2.0.0-F2-R1-HF3`.

Gates bloqueantes:

- versão F2;
- Compose DEV/PROD válido;
- endpoints de runtime;
- Alembic em `20260908_202_f2`;
- contrato de modelo MAIN/SUB;
- URLs RTSP sensíveis não serializadas;
- favoritos por usuário;
- status refresh limitado a 16 câmeras;
- frontend com AUTO/SUB/MAIN, grades 1/4/9/16 e fullscreen;
- WebRTC/HLS DEV em HTTP;
- suíte backend completa;
- build Web produzido pelo Docker durante atualização.

Gate final esperado:

`EDUVIGIA_F2_VMS_BASIC=APPROVED`
