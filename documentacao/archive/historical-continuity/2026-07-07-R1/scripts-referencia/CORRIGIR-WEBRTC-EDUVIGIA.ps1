$ErrorActionPreference = "Stop"

$ProjectPath = "C:\Users\ticon\Documents\eduvigia"
$ConfigPath = Join-Path $ProjectPath "mediamtx\mediamtx.yml"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupPath = "$ConfigPath.backup-webrtc-$Timestamp"
$Utf8SemBom = New-Object System.Text.UTF8Encoding($false)

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " CORRIGIR CONEXAO WEBRTC DO EDUVIGIA" -ForegroundColor Cyan
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

$IpLocal = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.InterfaceAlias -notmatch "vEthernet|Loopback|Bluetooth|Tailscale"
    } |
    Sort-Object InterfaceMetric |
    Select-Object -First 1 -ExpandProperty IPAddress

if (-not $IpLocal) {
    throw "Nao foi possivel detectar o IPv4 principal do computador."
}

Write-Host "IP principal detectado: $IpLocal" -ForegroundColor Green

Write-Host "[1/7] Criando backup..." -ForegroundColor Cyan
Copy-Item $ConfigPath $BackupPath -Force
Write-Host "Backup: $BackupPath" -ForegroundColor Green

Write-Host "[2/7] Configurando o endereco anunciado pelo WebRTC..." -ForegroundColor Cyan

$Original = Get-Content -LiteralPath $ConfigPath
$Result = New-Object System.Collections.Generic.List[string]
$Found = $false
$SkippingList = $false

for ($i = 0; $i -lt $Original.Count; $i++) {
    $Line = $Original[$i]

    if ($Line -match '^webrtcAdditionalHosts\s*:') {
        if (-not $Found) {
            [void]$Result.Add("webrtcAdditionalHosts: [`"$IpLocal`"]")
            $Found = $true
        }

        if ($Line.Trim() -eq "webrtcAdditionalHosts:") {
            $SkippingList = $true
        }

        continue
    }

    if ($SkippingList) {
        if ($Line -match '^\s*-\s*') {
            continue
        }

        if ($Line -match '^[^\s#][^:]*\s*:') {
            $SkippingList = $false
            [void]$Result.Add($Line)
        }
        else {
            continue
        }
    }
    else {
        [void]$Result.Add($Line)
    }
}

if (-not $Found) {
    $InsertIndex = -1

    for ($i = 0; $i -lt $Result.Count; $i++) {
        if ($Result[$i] -match '^webrtcAddress\s*:') {
            $InsertIndex = $i + 1
            break
        }
    }

    if ($InsertIndex -lt 0) {
        for ($i = 0; $i -lt $Result.Count; $i++) {
            if ($Result[$i] -match '^webrtc\s*:') {
                $InsertIndex = $i + 1
                break
            }
        }
    }

    if ($InsertIndex -lt 0) {
        $InsertIndex = 0
    }

    $Result.Insert($InsertIndex, "webrtcAdditionalHosts: [`"$IpLocal`"]")
}

[System.IO.File]::WriteAllLines($ConfigPath, $Result, $Utf8SemBom)
Write-Host "[OK] MediaMTX anunciara o host $IpLocal nas conexoes WebRTC." -ForegroundColor Green

Write-Host "[3/7] Garantindo regra de Firewall para WebRTC..." -ForegroundColor Cyan

$FirewallRules = @(
    @{ Name = "EduVigIA WebRTC HTTP 18889"; Protocol = "TCP"; Port = 18889 },
    @{ Name = "EduVigIA WebRTC ICE 18189"; Protocol = "UDP"; Port = 18189 }
)

foreach ($Rule in $FirewallRules) {
    if (-not (Get-NetFirewallRule -DisplayName $Rule.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule `
            -DisplayName $Rule.Name `
            -Direction Inbound `
            -Action Allow `
            -Protocol $Rule.Protocol `
            -LocalPort $Rule.Port `
            -Profile Private |
            Out-Null
    }
}

Write-Host "[OK] Regras de Firewall verificadas." -ForegroundColor Green

Write-Host "[4/7] Reiniciando apenas o MediaMTX..." -ForegroundColor Cyan

docker compose restart mediamtx
if ($LASTEXITCODE -ne 0) {
    Copy-Item $BackupPath $ConfigPath -Force
    docker compose restart mediamtx | Out-Null
    throw "Falha ao reiniciar o MediaMTX. O arquivo anterior foi restaurado."
}

Start-Sleep -Seconds 10

$Status = docker inspect -f "{{.State.Status}}" eduvigia_mediamtx 2>$null
if ($Status -ne "running") {
    docker compose logs mediamtx --tail=120
    Copy-Item $BackupPath $ConfigPath -Force
    docker compose restart mediamtx | Out-Null
    throw "O MediaMTX nao permaneceu ativo. A configuracao anterior foi restaurada."
}

Write-Host "[5/7] Reprovisionando a camera..." -ForegroundColor Cyan

$PythonCode = @'
from app.application import SessionLocal, Camera, provision_camera_path

db = SessionLocal()

try:
    cameras = db.query(Camera).order_by(Camera.id.asc()).all()

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

$Output = $PythonCode | docker compose exec -T api python -
$Output | ForEach-Object { Write-Host $_ }

if ($Output -match "Provisionado:\s+False") {
    throw "Uma ou mais cameras nao foram provisionadas."
}

Write-Host "[6/7] Confirmando que o stream esta pronto..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

$Paths = Invoke-RestMethod `
    -Uri "http://localhost:19997/v3/paths/list" `
    -TimeoutSec 20

$CameraPath = $Paths.items |
    Where-Object { $_.name -like "*cam-recife-main" -or $_.name -like "*cam-recife-sub" } |
    Select-Object -First 1

if ($CameraPath) {
    Write-Host "Stream: $($CameraPath.name)" -ForegroundColor White
    Write-Host "Ready: $($CameraPath.ready)" -ForegroundColor White
    Write-Host "Available: $($CameraPath.available)" -ForegroundColor White
    Write-Host "Tracks: $($CameraPath.tracks -join ', ')" -ForegroundColor White
}
else {
    Write-Host "[AVISO] Caminho da camera nao apareceu na consulta." -ForegroundColor Yellow
}

Write-Host "[7/7] Abrindo teste direto do WebRTC..." -ForegroundColor Cyan

$StreamName = if ($CameraPath) {
    $CameraPath.name
}
else {
    "esc-marechal-consta-cam-recife-main"
}

$DirectUrl = "http://localhost:18889/$StreamName"
$LanUrl = "http://$IpLocal`:18889/$StreamName"

Write-Host ""
Write-Host "Teste local: $DirectUrl" -ForegroundColor Yellow
Write-Host "Teste pela rede: $LanUrl" -ForegroundColor Yellow
Write-Host ""

Start-Process $DirectUrl

Write-Host "Aguardando 20 segundos para registrar a tentativa..." -ForegroundColor White
Start-Sleep -Seconds 20

Write-Host ""
Write-Host "LOGS WEBRTC MAIS RECENTES" -ForegroundColor Cyan
docker compose logs mediamtx --since=2m |
    Select-String "WebRTC|ICE|peer|candidate|closed|error|failed"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " AJUSTE WEBRTC APLICADO" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Depois teste o monitoramento:" -ForegroundColor White
Write-Host "http://localhost:5177/#/monitor" -ForegroundColor Yellow
Write-Host ""
Write-Host "Pressione Ctrl + Shift + R." -ForegroundColor White
