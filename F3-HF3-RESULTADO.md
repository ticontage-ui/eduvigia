# EduVigIA — F3-R1-HF3 — Bootstrap Docker/PowerShell 5.1

## Objetivo
Corrigir a falsa falha do bootstrap F3 em Windows PowerShell 5.1 quando `docker compose run` escreve mensagens informativas em stderr, inclusive na geração do certificado TLS e nas migrations Alembic.

## Alteração
- Nenhuma migration nova.
- Nenhuma alteração funcional no PTZ/VMS.
- `SUBIR-EDUVIGIA.ps1` passa a decidir sucesso/falha dos `docker compose run` críticos pelo exit code real de `docker.exe`.
- `Invoke-DockerPassthrough` protege certgen e Alembic `stamp/upgrade`.
- `Invoke-DockerProbe` e `Invoke-DockerCapture` permanecem para probes/captura silenciosa.
- Novos marcadores: `TLS_CERT_DOCKER_RUN_PS51_SAFE` e `ALL_BOOTSTRAP_DOCKER_RUN_PS51_SAFE`.
- O gate `PS51_DOCKER_STDERR_COMPAT` exige que não existam chamadas cruas `docker compose run` no bootstrap.

## Origem aceita
`2.0.0-F3-R1-HF2`, `2.0.0-F3-R1-HF1`, `2.0.0-F3-R1`, `2.0.0-F2-R1-HF3`.

## Resultado esperado
- `EDUVIGIA_F3_PTZ_CORE=APPROVED`
- `EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST`
- `EDUVIGIA_F3_HF3_PS51_DOCKER_RUN=APPROVED`
- `EDUVIGIA_F3_HF3_UPDATE=APPROVED`
- `BASELINE=2.0.0-F3-R1-HF4`
