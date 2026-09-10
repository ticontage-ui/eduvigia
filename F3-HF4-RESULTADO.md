# EduVigIA 2.0.0-F3-R1-HF4 — Resultado técnico

## Objetivo
Corrigir o bootstrap da F3 após falha `exec /usr/local/bin/python: argument list too long` durante o certgen executado por `docker compose run`.

## Correção
- Certgen executado com `docker run` usando ambiente mínimo e somente volume `/certs`.
- Probe PostgreSQL executado com `docker run` usando somente `DATABASE_URL` e a rede do PostgreSQL.
- Alembic probe/stamp/upgrade executados com `docker run` usando somente `DATABASE_URL` e a rede do PostgreSQL.
- Nenhum `docker compose run` é usado no bootstrap de subida.
- Migration F3 continua ocorrendo antes do primeiro boot da API.
- Compatibilidade com Windows PowerShell 5.1 preservada pelos wrappers baseados no exit code real do Docker.

## Alteração funcional
Nenhuma alteração funcional no VMS/PTZ e nenhuma migration nova.

## Validação local
- Backend regression: 56 passed / 0 failed.
- Python compile: aprovado.
- Versão: 2.0.0-F3-R1-HF4.
- Release sem `.env`, banco SQLite, chaves privadas, node_modules ou caches.

## Estado
Candidato para homologação Windows/Docker.

Gate esperado:
- `EDUVIGIA_F3_PTZ_CORE=APPROVED`
- `EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST`
- `EDUVIGIA_F3_HF4_ARGMAX_BOOTSTRAP=APPROVED`
- `EDUVIGIA_F3_HF4_UPDATE=APPROVED`
