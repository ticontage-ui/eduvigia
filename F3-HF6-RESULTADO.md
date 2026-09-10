# EduVigIA 2.0.0-F3-R1-HF6 — Resultado técnico

## Objetivo
Corrigir a falha real de inicialização do PostgreSQL observada no HF5:

`exec /usr/local/bin/docker-entrypoint.sh: argument list too long`

## Causa confirmada
Os serviços `postgres` e `api` usavam `env_file: .env`. O Docker injetava o conteúdo completo do arquivo `.env` dentro dos containers, inclusive variáveis que esses serviços não utilizavam. Com o crescimento do ambiente, o processo de entrada do PostgreSQL ultrapassou o limite de argumentos/ambiente do kernel antes mesmo de iniciar o banco.

A evidência de campo foi `Restarting (255)` no container `eduvigia_postgres` e a repetição de `argument list too long` no `docker-entrypoint.sh`.

## Correção
- Removido `env_file: .env` do serviço `postgres` em DEV e PROD.
- Removido `env_file: .env` do serviço `api` em DEV e PROD.
- PostgreSQL passa a receber apenas `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` pela seção `environment`.
- API passa a receber uma allowlist explícita somente das variáveis realmente utilizadas pelo runtime.
- O `.env` continua no host para interpolação do Compose, mas deixa de ser despejado integralmente nos containers.
- Homologador valida `NO_RUNTIME_ENV_FILE`, `POSTGRES_ENV_ALLOWLIST`, `API_ENV_ALLOWLIST` e `POSTGRES_RUNTIME_ENV_MINIMAL`.
- Instalador informa apenas tamanho do `.env` e maior linha, sem revelar valores, e bloqueia somente variáveis críticas com tamanho manifestamente anormal.

## Alteração funcional
Nenhuma alteração funcional no VMS/PTZ e nenhuma migration nova.

## Validação local
- Backend regression: 56 passed / 0 failed.
- Compose DEV YAML: aprovado.
- Compose PROD YAML: aprovado.
- `env_file` ausente em `postgres` e `api` nos dois Compose.
- PostgreSQL environment allowlist: aprovada.
- API environment allowlist: aprovada.
- Release scan: sem `.env`, chaves privadas, banco local, `node_modules` ou caches.
- Versão: `2.0.0-F3-R1-HF6`.

## Estado
Candidato para homologação Windows/Docker.

Gate esperado:
- `EDUVIGIA_F3_PTZ_CORE=APPROVED`
- `EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST`
- `EDUVIGIA_F3_HF6_ENV_ALLOWLIST=APPROVED`
- `EDUVIGIA_F3_HF6_UPDATE=APPROVED`
- `BASELINE=2.0.0-F3-R1-HF6`
