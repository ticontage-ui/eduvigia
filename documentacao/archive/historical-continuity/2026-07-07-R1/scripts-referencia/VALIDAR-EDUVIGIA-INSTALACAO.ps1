$ErrorActionPreference = "Stop"

$ProjectPath = "C:\Users\ticon\Documents\eduvigia"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " VALIDACAO CORRETA DA INSTALACAO EDUVIGIA" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ProjectPath)) {
    throw "Projeto nao encontrado: $ProjectPath"
}

Set-Location $ProjectPath

Write-Host "[1/6] Verificando containers..." -ForegroundColor Cyan
docker compose ps

Write-Host "[2/6] Aguardando frontend ficar saudavel..." -ForegroundColor Cyan
$WebHealthy = $false

for ($i = 1; $i -le 18; $i++) {
    $Status = docker inspect -f "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" eduvigia_web 2>$null

    if ($Status -eq "healthy") {
        $WebHealthy = $true
        Write-Host "[OK] Frontend saudavel." -ForegroundColor Green
        break
    }

    Write-Host "Tentativa $i/18 - status: $Status" -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

if (-not $WebHealthy) {
    Write-Host "[AVISO] O frontend ainda nao informou healthy, mas sera testado via HTTP." -ForegroundColor Yellow
}

function Testar-Http {
    param(
        [string]$Nome,
        [string]$Url,
        [int[]]$StatusAceitos = @(200)
    )

    try {
        $Resposta = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 20
        if ($StatusAceitos -contains [int]$Resposta.StatusCode) {
            Write-Host "[OK] $Nome - HTTP $($Resposta.StatusCode)" -ForegroundColor Green
            return $true
        }

        Write-Host "[FALHA] $Nome - HTTP $($Resposta.StatusCode)" -ForegroundColor Red
        return $false
    }
    catch {
        $StatusCode = $null
        if ($_.Exception.Response) {
            try {
                $StatusCode = [int]$_.Exception.Response.StatusCode
            } catch {}
        }

        if ($StatusCode -and ($StatusAceitos -contains $StatusCode)) {
            Write-Host "[OK] $Nome - HTTP $StatusCode" -ForegroundColor Green
            return $true
        }

        Write-Host "[FALHA] $Nome - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host "[3/6] Validando aplicacao..." -ForegroundColor Cyan
$Resultados = @()
$Resultados += Testar-Http -Nome "Painel Web" -Url "http://localhost:5177"
$Resultados += Testar-Http -Nome "API Health" -Url "http://localhost:8002/health"
$Resultados += Testar-Http -Nome "Swagger" -Url "http://localhost:8002/docs"

Write-Host "[4/6] Validando stream de teste..." -ForegroundColor Cyan

$RtspOk = Test-NetConnection localhost -Port 18554 -WarningAction SilentlyContinue
if ($RtspOk.TcpTestSucceeded) {
    Write-Host "[OK] Porta RTSP 18554 acessivel." -ForegroundColor Green
    $Resultados += $true
} else {
    Write-Host "[FALHA] Porta RTSP 18554 indisponivel." -ForegroundColor Red
    $Resultados += $false
}

$Resultados += Testar-Http -Nome "HLS do stream teste" -Url "http://localhost:18888/teste/index.m3u8"
$Resultados += Testar-Http -Nome "WebRTC do stream teste" -Url "http://localhost:18889/teste"

Write-Host "[5/6] Consultando MediaMTX..." -ForegroundColor Cyan
$Resultados += Testar-Http -Nome "MediaMTX API" -Url "http://localhost:19997/v3/paths/list"
$Resultados += Testar-Http -Nome "MediaMTX Metrics" -Url "http://localhost:19998/metrics"

Write-Host "[6/6] Resultado final..." -ForegroundColor Cyan

if ($Resultados -contains $false) {
    Write-Host ""
    Write-Host "A instalacao principal esta ativa, mas algum teste complementar falhou." -ForegroundColor Yellow
    Write-Host "Logs do MediaMTX:" -ForegroundColor Yellow
    docker compose logs mediamtx --tail=120
    Write-Host ""
    Write-Host "Logs do video de teste:" -ForegroundColor Yellow
    docker compose logs video_teste --tail=120
    exit 1
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " EDUVIGIA INSTALADO E VALIDADO COM SUCESSO" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Painel:  http://localhost:5177" -ForegroundColor Yellow
Write-Host "API:     http://localhost:8002/health" -ForegroundColor Yellow
Write-Host "Swagger: http://localhost:8002/docs" -ForegroundColor Yellow
Write-Host "HLS:     http://localhost:18888/teste/index.m3u8" -ForegroundColor Yellow
Write-Host "WebRTC:  http://localhost:18889/teste" -ForegroundColor Yellow
Write-Host "RTSP:    rtsp://localhost:18554/teste" -ForegroundColor Yellow
