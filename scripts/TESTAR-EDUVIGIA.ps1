$ErrorActionPreference = "Stop"
$Project = Join-Path $env:USERPROFILE "Documents\eduvigia"
Set-Location $Project

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " TESTES AUTOMATIZADOS EDUVIGIA" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

docker compose up -d postgres redis
docker compose build api
docker compose run --rm api pytest -q

if ($LASTEXITCODE -ne 0) {
    throw "Um ou mais testes falharam."
}

Write-Host "Todos os testes automatizados foram aprovados." -ForegroundColor Green
