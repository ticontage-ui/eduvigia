[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Project = Join-Path $env:USERPROFILE "Documents\eduvigia"
if (-not (Test-Path (Join-Path $Project "docker-compose.yml"))) {
    throw "Projeto não localizado em $Project"
}

Push-Location $Project
try {
    docker compose ps
    $health = Invoke-RestMethod -Uri "http://localhost:8002/health" -TimeoutSec 15
    if ($health.version -ne "1.8.5-R1") {
        throw "Versão incorreta: $($health.version)"
    }

    $anonymousDenied = $false
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:18889/teste" -TimeoutSec 20 | Out-Null
    } catch {
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -in @(401, 403)) { $anonymousDenied = $true }
    }
    if (-not $anonymousDenied) {
        throw "Leitura anônima do MediaMTX não foi bloqueada."
    }

    Write-Host "EduVigIA 1.8.5-R1: API correta e leitura anônima bloqueada." -ForegroundColor Green
} finally {
    Pop-Location
}
