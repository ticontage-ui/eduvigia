$ErrorActionPreference = "Continue"
$Project = Join-Path $env:USERPROFILE "Documents\eduvigia"
$Output = Join-Path $env:USERPROFILE ("Downloads\DIAGNOSTICO-EDUVIGIA-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")
Set-Location $Project
"EDUVIGIA 2.0.0-F7-R2 - DIAGNOSTICO" | Set-Content $Output
"Data: $(Get-Date)" | Add-Content $Output
"" | Add-Content $Output
"=== COMPOSE PS ===" | Add-Content $Output
docker compose ps -a 2>&1 | Out-String | Add-Content $Output
"=== COMPOSE CONFIG VALIDATION ===" | Add-Content $Output
docker compose config --quiet 2>&1 | Out-String | Add-Content $Output
foreach ($Service in @("api", "web", "proxy", "prometheus", "postgres", "redis", "mediamtx")) {
    "=== LOGS $Service ===" | Add-Content $Output
    docker compose logs $Service --tail=120 2>&1 | Out-String | Add-Content $Output
}
"=== ENDPOINTS ===" | Add-Content $Output
foreach ($Url in @("http://localhost:8002/live", "http://localhost:8002/ready", "http://localhost:8002/metrics", "http://localhost:8088/healthz", "http://localhost:19090/-/ready")) {
    try { Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10 | Select-Object StatusCode,Headers | Out-String | Add-Content $Output }
    catch { $_.Exception.Message | Add-Content $Output }
}
Write-Host "Diagnóstico salvo em: $Output" -ForegroundColor Green
