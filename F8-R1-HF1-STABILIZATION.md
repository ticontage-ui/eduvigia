# EduVigIA 2.0.0-F8-R1 — HF1 Stabilization

Objetivo: estabilização pré-homologação da F8 sem alteração das regras de negócio do SOS.

## Escopo

- alinhar metadados de versão do repositório e runtime para `2.0.0-F8-R1`;
- corrigir versão exibida no login;
- alinhar defaults dos Compose, `.env.example`, config e scripts de diagnóstico/backup;
- alinhar `APP_VERSION` do `.env` local, sem versionar ou copiar segredos;
- adicionar `backend/tests/conftest.py` para tornar a suíte reproduzível em checkout limpo;
- adicionar `backend/Dockerfile.test` para regressão isolada em Python 3.12;
- preservar a migration `20260915_210_f8_sos`;
- não alterar RBAC, estados, deduplicação, alerta, ocorrência, timeline ou auditoria do SOS.

## Gate

A F8 continua **não homologada** até concluir o Browser QA funcional.

Resultado esperado da regressão: `107 passed`.