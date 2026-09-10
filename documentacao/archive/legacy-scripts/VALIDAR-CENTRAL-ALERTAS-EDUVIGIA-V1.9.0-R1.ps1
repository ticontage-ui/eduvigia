[CmdletBinding()]
param(
    [string]$ProjectPath = "$env:USERPROFILE\Documents\eduvigia"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $ProjectPath "docker-compose.yml"))) {
    throw "Projeto EduVigIA não encontrado em $ProjectPath"
}

Set-Location -LiteralPath $ProjectPath

docker compose exec -T api python -m app.alert_center_preflight
if ($LASTEXITCODE -ne 0) { throw "Preflight da Central de Alertas reprovado." }

Write-Host "" 
Write-Host "Métricas da Central de Alertas:" -ForegroundColor Cyan
$metrics = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8002/metrics" -TimeoutSec 15
$metrics.Content -split "`n" | Where-Object { $_ -match '^eduvigia_alerts_' }

Write-Host "" 
Write-Host "Central de Alertas validada." -ForegroundColor Green
Write-Host "Painel: http://localhost:5177" -ForegroundColor White
