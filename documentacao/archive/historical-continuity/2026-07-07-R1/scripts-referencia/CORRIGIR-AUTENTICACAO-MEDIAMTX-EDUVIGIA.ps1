$ErrorActionPreference = "Stop"

$ProjectPath = "C:\Users\ticon\Documents\eduvigia"
$ConfigPath = Join-Path $ProjectPath "mediamtx\mediamtx.yml"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupPath = "$ConfigPath.backup-$Timestamp"
$Utf8SemBom = New-Object System.Text.UTF8Encoding($false)

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " CORRECAO DE AUTENTICACAO MEDIAMTX - EDUVIGIA" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ProjectPath)) {
    throw "Projeto nao encontrado: $ProjectPath"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Configuracao do MediaMTX nao encontrada: $ConfigPath"
}

Set-Location $ProjectPath

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop nao esta operacional."
}

Write-Host "[1/8] Criando backup da configuracao..." -ForegroundColor Cyan
Copy-Item $ConfigPath $BackupPath -Force
Write-Host "Backup: $BackupPath" -ForegroundColor Green

Write-Host "[2/8] Verificando metodo de autenticacao..." -ForegroundColor Cyan
$Lines = [System.Collections.Generic.List[string]]::new()
Get-Content -LiteralPath $ConfigPath | ForEach-Object { [void]$Lines.Add($_) }

$AuthMethodLine = $Lines | Where-Object { $_ -match '^\s*authMethod\s*:\s*(\S+)\s*$' } | Select-Object -First 1
if ($AuthMethodLine -and $AuthMethodLine -notmatch '^\s*authMethod\s*:\s*internal\s*$') {
    throw "O MediaMTX nao usa authMethod internal. Nenhuma alteracao foi aplicada. Metodo encontrado: $AuthMethodLine"
}

$Marker = "# EDUVIGIA_LOCAL_CONTROL_API"
if ($Lines -contains $Marker -or ($Lines -join "`n") -match [regex]::Escape($Marker)) {
    Write-Host "[OK] Regra local da API ja existe." -ForegroundColor Green
}
else {
    $AuthIndex = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match '^authInternalUsers\s*:\s*$') {
            $AuthIndex = $i
            break
        }
    }

    $Entry = @(
        "  $Marker",
        "  - user: any",
        "    pass:",
        "    ips: ['127.0.0.1', '::1', '172.16.0.0/12']",
        "    permissions:",
        "      - action: api",
        "      - action: metrics",
        "      - action: pprof"
    )

    if ($AuthIndex -ge 0) {
        $InsertIndex = $Lines.Count

        for ($i = $AuthIndex + 1; $i -lt $Lines.Count; $i++) {
            $Line = $Lines[$i]

            if ($Line -match '^[^\s#][^:]*\s*:') {
                $InsertIndex = $i
                break
            }
        }

        for ($j = $Entry.Count - 1; $j -ge 0; $j--) {
            $Lines.Insert($InsertIndex, $Entry[$j])
        }
    }
    else {
        $NewSection = @("authMethod: internal", "", "authInternalUsers:") + $Entry + @("")
        $InsertIndex = 0

        for ($j = $NewSection.Count - 1; $j -ge 0; $j--) {
            $Lines.Insert($InsertIndex, $NewSection[$j])
        }
    }

    [System.IO.File]::WriteAllLines($ConfigPath, $Lines, $Utf8SemBom)
    Write-Host "[OK] Permissao local para API e metricas adicionada." -ForegroundColor Green
}

Write-Host "[3/8] Validando a configuracao no container..." -ForegroundColor Cyan
docker compose up -d mediamtx
if ($LASTEXITCODE -ne 0) {
    Copy-Item $BackupPath $ConfigPath -Force
    throw "O MediaMTX nao iniciou. A configuracao anterior foi restaurada."
}

Start-Sleep -Seconds 8

$MediaStatus = docker inspect -f "{{.State.Status}}" eduvigia_mediamtx 2>$null
if ($MediaStatus -ne "running") {
    docker compose logs mediamtx --tail=120
    Copy-Item $BackupPath $ConfigPath -Force
    docker compose restart mediamtx | Out-Null
    throw "O MediaMTX nao permaneceu ativo. A configuracao anterior foi restaurada."
}

Write-Host "[4/8] Testando API e metricas do MediaMTX..." -ForegroundColor Cyan
try {
    $ConfigResponse = Invoke-RestMethod `
        -Uri "http://localhost:19997/v3/config/paths/list" `
        -TimeoutSec 20

    Write-Host "[OK] Control API respondeu sem erro 401." -ForegroundColor Green
}
catch {
    Write-Host "[FALHA] Control API ainda bloqueada." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    throw "A autenticacao do MediaMTX ainda nao foi liberada."
}

try {
    $MetricsResponse = Invoke-WebRequest `
        -Uri "http://localhost:19998/metrics" `
        -UseBasicParsing `
        -TimeoutSec 20

    Write-Host "[OK] Metricas HTTP $($MetricsResponse.StatusCode)" -ForegroundColor Green
}
catch {
    Write-Host "[AVISO] Metricas ainda nao responderam: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "[5/8] Reprovisionando cameras cadastradas..." -ForegroundColor Cyan

$PythonCode = @'
from app.application import SessionLocal, Camera, provision_camera_path

db = SessionLocal()

try:
    cameras = db.query(Camera).order_by(Camera.id.asc()).all()

    if not cameras:
        print("Nenhuma camera cadastrada.")

    for camera in cameras:
        ok, detail = provision_camera_path(camera, db)
        camera.last_error = None if ok else str(detail)

        print("")
        print("Camera ID:", camera.id)
        print("Nome:", camera.name)
        print("Stream:", camera.stream_name)
        print("Provisionado:", ok)
        print("Detalhe:", detail)

    db.commit()

finally:
    db.close()
'@

$ProvisionOutput = $PythonCode | docker compose exec -T api python -
$ProvisionOutput | ForEach-Object { Write-Host $_ }

if ($ProvisionOutput -match "Provisionado:\s+False") {
    Write-Host ""
    Write-Host "A API do MediaMTX foi corrigida, mas a camera ainda recusou o provisionamento." -ForegroundColor Yellow
    Write-Host "Nesse caso, revise no cadastro da camera o usuario e a senha RTSP." -ForegroundColor Yellow
}

Write-Host "[6/8] Aguardando o MediaMTX abrir os streams..." -ForegroundColor Cyan
Start-Sleep -Seconds 12

Write-Host "[7/8] Listando caminhos ativos..." -ForegroundColor Cyan
try {
    $Paths = Invoke-RestMethod `
        -Uri "http://localhost:19997/v3/paths/list" `
        -TimeoutSec 20

    $Paths | ConvertTo-Json -Depth 12
}
catch {
    Write-Host "[AVISO] Nao foi possivel listar os caminhos ativos." -ForegroundColor Yellow
    Write-Host $_.Exception.Message
}

Write-Host "[8/8] Exibindo logs finais do MediaMTX..." -ForegroundColor Cyan
docker compose logs mediamtx --tail=120

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " CORRECAO CONCLUIDA" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Abra novamente:" -ForegroundColor White
Write-Host "http://localhost:5177/#/monitor" -ForegroundColor Yellow
Write-Host ""
Write-Host "Depois pressione Ctrl + Shift + R." -ForegroundColor White
