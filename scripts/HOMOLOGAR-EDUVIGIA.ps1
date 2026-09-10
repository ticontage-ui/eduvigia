$ErrorActionPreference = "Stop"
$Project = Join-Path $env:USERPROFILE "Documents\eduvigia"
$Report = Join-Path $env:USERPROFILE ("Downloads\RELATORIO-HOMOLOGACAO-EDUVIGIA-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")
Set-Location $Project

"RELATORIO DE HOMOLOGACAO EDUVIGIA" | Set-Content $Report
"Data: $(Get-Date)" | Add-Content $Report
"" | Add-Content $Report

"=== CONTAINERS ===" | Add-Content $Report
docker compose ps 2>&1 | Out-String | Add-Content $Report

"=== PORTAS ===" | Add-Content $Report
foreach ($Port in @(5177,8002,5437,6382,18554,18888,18889,19997,19998)) {
    Test-NetConnection localhost -Port $Port -WarningAction SilentlyContinue |
        Select-Object RemotePort,TcpTestSucceeded |
        Out-String | Add-Content $Report
}

"=== TESTES AUTOMATIZADOS ===" | Add-Content $Report
docker compose run --rm api pytest -q 2>&1 | Out-String | Add-Content $Report

Write-Host "Relatório gerado em: $Report" -ForegroundColor Green
