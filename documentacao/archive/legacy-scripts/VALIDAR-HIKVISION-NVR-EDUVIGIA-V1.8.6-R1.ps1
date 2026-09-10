[CmdletBinding()]
param(
    [string]$ProjectPath = (Join-Path $env:USERPROFILE "Documents\eduvigia")
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $ProjectPath "docker-compose.yml"))) {
    throw "Projeto EduVigIA não localizado em: $ProjectPath"
}

Push-Location $ProjectPath
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8002/health" -TimeoutSec 15
    if ($health.version -ne "1.8.6-R1") {
        throw "Versão da API incorreta: $($health.version)"
    }

    docker compose exec -T api python -m app.nvr_preflight
    if ($LASTEXITCODE -ne 0) {
        throw "Pré-validação interna Hikvision/NVR reprovada."
    }

    docker compose ps
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao consultar os serviços Docker."
    }

    Write-Host "EduVigIA 1.8.6-R1: integração Hikvision/NVR validada." -ForegroundColor Green
    Write-Host "A validação física de câmera/NVR deve ser concluída na interface Câmeras e Gravadores." -ForegroundColor Yellow
} finally {
    Pop-Location
}
