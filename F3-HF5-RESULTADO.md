# EduVigIA 2.0.0-F3-R1-HF5 — Resultado técnico

## Objetivo
Corrigir a falha de bootstrap `Imagem da API não localizada após o build` observada no HF4.

## Causa
O bootstrap usava `docker compose images -q api` para descobrir a imagem recém-buildada. Esse comando pode retornar vazio quando o serviço ainda não possui container criado, mesmo com `docker compose build api` concluído com sucesso.

## Correção
- O serviço `api` agora possui imagem explícita e determinística: `eduvigia-api:latest` em DEV e PROD.
- O bootstrap usa `docker image inspect eduvigia-api:latest` para validar a imagem após o build.
- O certgen, probe PostgreSQL e Alembic continuam usando `docker run` com ambiente mínimo.
- O homologador também usa `eduvigia-api:latest`, sem depender de `docker compose images`.
- Novo marcador: `PASS|API_IMAGE_DETERMINISTIC`.

## Alteração funcional
Nenhuma alteração funcional no VMS/PTZ e nenhuma migration nova.

## Validação local
- Backend regression: 56 passed / 0 failed.
- Compose DEV YAML: aprovado.
- Compose PROD YAML: aprovado.
- API image contract: `eduvigia-api:latest` presente em ambos os Compose.
- Python compile / release scan: aprovado.
- Versão: `2.0.0-F3-R1-HF5`.

## Estado
Candidato para homologação Windows/Docker.

Gate esperado:
- `EDUVIGIA_F3_PTZ_CORE=APPROVED`
- `EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST`
- `EDUVIGIA_F3_HF5_IMAGE_DISCOVERY=APPROVED`
- `EDUVIGIA_F3_HF5_UPDATE=APPROVED`
- `BASELINE=2.0.0-F3-R1-HF5`
