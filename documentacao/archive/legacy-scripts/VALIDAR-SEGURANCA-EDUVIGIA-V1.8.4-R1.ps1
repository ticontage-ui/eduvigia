[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $Project
try {
    Write-Host '[1/4] Validando Docker Compose...' -ForegroundColor Cyan
    docker compose config | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'docker compose config falhou.' }

    Write-Host '[2/4] Construindo API e Web...' -ForegroundColor Cyan
    docker compose build api web
    if ($LASTEXITCODE -ne 0) { throw 'Build da API ou Web falhou.' }

    Write-Host '[3/4] Executando testes de segurança...' -ForegroundColor Cyan
    docker compose run --rm --no-deps `
        -e DATABASE_URL=sqlite:////tmp/eduvigia-security-tests.db `
        -e EDUVIGIA_DATA_DIR=/tmp/eduvigia-data `
        -e EDUVIGIA_CREDENTIAL_KEY=MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA= `
        -e EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD=SenhaTeste@2026! `
        api pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Testes de segurança falharam.' }

    Write-Host '[4/4] Resultado: APROVADO' -ForegroundColor Green
}
finally {
    Pop-Location
}
