# Matriz de Homologação — F2-R1-HF3

Baseline candidata: `2.0.0-F2-R1-HF3`.

| Gate | Critério |
|---|---|
| F2 base | Contratos VMS F2 aprovados |
| Runtime | Painel/API/Proxy/Prometheus operacionais |
| Alembic | Head `20260908_202_f2` |
| Runner import | `import app` e `import app.application` aprovados no container efêmero |
| Backend regression | suíte executada com `python -m pytest` |
| DB isolation | SQLite temporário diferente do `DATABASE_URL` runtime |
| Read-only mounts | `backend/app` e `backend/tests` montados `:ro` |
| Web | container web operacional após build |

A fase só é homologada com zero falhas.
