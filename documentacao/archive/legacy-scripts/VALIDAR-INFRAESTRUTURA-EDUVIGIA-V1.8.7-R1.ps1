$ErrorActionPreference = "Stop"
$Project = Join-Path $env:USERPROFILE "Documents\eduvigia"
if (-not (Test-Path (Join-Path $Project "docker-compose.yml"))) { throw "Projeto não localizado: $Project" }
Set-Location $Project

$Health = Invoke-RestMethod -Uri "http://localhost:8002/health" -TimeoutSec 15
if ($Health.version -ne "1.8.7-R1") { throw ("Versão incorreta: {0}" -f $Health.version) }
$Live = Invoke-RestMethod -Uri "http://localhost:8002/live" -TimeoutSec 15
if ($Live.status -ne "alive") { throw "Liveness reprovada." }
$Ready = Invoke-RestMethod -Uri "http://localhost:8002/ready" -TimeoutSec 15
if (-not $Ready.ready) { throw "Readiness reprovada." }
$Metrics = (Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8002/metrics" -TimeoutSec 15).Content
foreach ($Metric in @("eduvigia_info", "eduvigia_database_up 1", "eduvigia_http_requests_total")) {
    if ($Metrics -notmatch [regex]::Escape($Metric)) { throw ("Métrica ausente: {0}" -f $Metric) }
}
$Proxy = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8088/healthz" -TimeoutSec 15
if ($Proxy.StatusCode -ne 200) { throw "Proxy HTTP reprovado." }
$Prometheus = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:19090/-/ready" -TimeoutSec 15
if ($Prometheus.StatusCode -ne 200) { throw "Prometheus reprovado." }
if (-not (Test-NetConnection localhost -Port 8443 -WarningAction SilentlyContinue).TcpTestSucceeded) { throw "Proxy HTTPS indisponível." }
docker compose exec -T api python -m app.infrastructure_preflight
if ($LASTEXITCODE -ne 0) { throw "Preflight interno de infraestrutura reprovado." }
Write-Host "INFRAESTRUTURA_EDUVIGIA_1.8.7_R1_OK" -ForegroundColor Green
