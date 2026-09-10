# EduVigIA 2.0.0-F2-R1-HF3 — Correção do gate de isolamento F2

## Motivo
O HF2 executou a regressão isolada com sucesso (`49 passed`), porém o gate `TEST_GATE_ISOLATED_FROM_RUNTIME_DB` se reprovava por uma verificação autorreferente: o próprio texto proibido pesquisado pelo `-notmatch` existia dentro da expressão de validação.

## Correção
- nenhuma alteração funcional no VMS;
- nenhuma migration nova;
- preserva MAIN/SUB, AUTO, mosaicos, favoritos, status e reconexão;
- regressão continua em container efêmero com SQLite temporário;
- `backend/app` e `backend/tests` continuam read-only;
- `PYTHONPATH=/app`, `--workdir /app`, `--no-deps` e `python -m pytest` preservados;
- gate de isolamento agora verifica objetivamente o `DATABASE_URL` runtime versus SQLite temporário e os mounts read-only, sem inspecionar o próprio texto do script.

## Gate final esperado
- `EDUVIGIA_F2_VMS_BASIC=APPROVED`
- `EDUVIGIA_F2_HF3_TEST_GATE=APPROVED`
- `EDUVIGIA_F2_HF3_UPDATE=APPROVED`
- `BASELINE=2.0.0-F2-R1-HF3`
