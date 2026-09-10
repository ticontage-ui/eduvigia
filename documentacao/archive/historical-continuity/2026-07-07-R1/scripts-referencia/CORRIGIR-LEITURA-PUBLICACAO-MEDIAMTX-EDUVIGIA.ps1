$ErrorActionPreference = "Stop"

$ProjectPath = "C:\Users\ticon\Documents\eduvigia"
$ConfigPath = Join-Path $ProjectPath "mediamtx\mediamtx.yml"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupPath = "$ConfigPath.backup-auth-$Timestamp"
$Utf8SemBom = New-Object System.Text.UTF8Encoding($false)

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " CORRIGIR LEITURA E PUBLICACAO DO MEDIAMTX" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ProjectPath)) {
    throw "Projeto nao encontrado: $ProjectPath"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Arquivo nao encontrado: $ConfigPath"
}

Set-Location $ProjectPath

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop nao esta operacional."
}

Write-Host "[1/9] Criando backup da configuracao..." -ForegroundColor Cyan
Copy-Item $ConfigPath $BackupPath -Force
Write-Host "Backup: $BackupPath" -ForegroundColor Green

Write-Host "[2/9] Recriando o bloco de autenticacao..." -ForegroundColor Cyan

$Original = Get-Content -LiteralPath $ConfigPath
$Clean = New-Object System.Collections.Generic.List[string]

$SkippingAuthUsers = $false

for ($i = 0; $i -lt $Original.Count; $i++) {
    $Line = $Original[$i]

    if ($Line -match '^authMethod\s*:') {
        continue
    }

    if ($Line -match '^authInternalUsers\s*:') {
        $SkippingAuthUsers = $true
        continue
    }

    if ($SkippingAuthUsers) {
        # O bloco termina quando aparece outra chave YAML de nivel superior.
        if ($Line -match '^[^\s#][^:]*\s*:') {
            $SkippingAuthUsers = $false
            [void]$Clean.Add($Line)
        }
        else {
            continue
        }
    }
    else {
        [void]$Clean.Add($Line)
    }
}

$AuthBlock = @(
    "authMethod: internal",
    "",
    "authInternalUsers:",
    "  # Leitura, publicacao e playback para a operacao local do EduVigIA.",
    "  - user: any",
    "    pass:",
    "    ips: ['127.0.0.1', '::1', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']",
    "    permissions:",
    "      - action: publish",
    "      - action: read",
    "      - action: playback",
    "",
    "  # Control API e metricas somente para localhost e rede interna Docker.",
    "  - user: any",
    "    pass:",
    "    ips: ['127.0.0.1', '::1', '172.16.0.0/12']",
    "    permissions:",
    "      - action: api",
    "      - action: metrics",
    "      - action: pprof",
    ""
)

$Final = New-Object System.Collections.Generic.List[string]
foreach ($Line in $AuthBlock) {
    [void]$Final.Add($Line)
}
foreach ($Line in $Clean) {
    [void]$Final.Add($Line)
}

[System.IO.File]::WriteAllLines($ConfigPath, $Final, $Utf8SemBom)
Write-Host "[OK] Permissoes de publish, read, playback, api e metrics configuradas." -ForegroundColor Green

Write-Host "[3/9] Reiniciando MediaMTX e video de teste..." -ForegroundColor Cyan
docker compose restart mediamtx
if ($LASTEXITCODE -ne 0) {
    Copy-Item $BackupPath $ConfigPath -Force
    throw "Falha ao reiniciar o MediaMTX. A configuracao anterior foi restaurada."
}

Start-Sleep -Seconds 6

docker compose restart video_teste
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao reiniciar o video de teste."
}

Start-Sleep -Seconds 10

$MediaStatus = docker inspect -f "{{.State.Status}}" eduvigia_mediamtx 2>$null
if ($MediaStatus -ne "running") {
    docker compose logs mediamtx --tail=150
    Copy-Item $BackupPath $ConfigPath -Force
    docker compose restart mediamtx | Out-Null
    throw "O MediaMTX nao permaneceu ativo. A configuracao anterior foi restaurada."
}

Write-Host "[4/9] Validando Control API e metricas..." -ForegroundColor Cyan
try {
    $null = Invoke-RestMethod `
        -Uri "http://localhost:19997/v3/config/paths/list" `
        -TimeoutSec 20

    Write-Host "[OK] Control API autorizada." -ForegroundColor Green
}
catch {
    throw "Control API falhou: $($_.Exception.Message)"
}

try {
    $Metrics = Invoke-WebRequest `
        -Uri "http://localhost:19998/metrics" `
        -UseBasicParsing `
        -TimeoutSec 20

    Write-Host "[OK] Metricas HTTP $($Metrics.StatusCode)" -ForegroundColor Green
}
catch {
    throw "Metricas falharam: $($_.Exception.Message)"
}

Write-Host "[5/9] Validando publicacao e leitura do stream de teste..." -ForegroundColor Cyan

$TesteCodigo = @'
import subprocess
import sys

cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "error",
    "-rtsp_transport", "tcp",
    "-i", "rtsp://mediamtx:8554/teste",
    "-frames:v", "1",
    "-f", "null",
    "-"
]

p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)

print("Retorno:", p.returncode)

if p.stderr:
    print(p.stderr[-1200:])

sys.exit(p.returncode)
'@

$TesteCodigo | docker compose exec -T api python -
if ($LASTEXITCODE -ne 0) {
    docker compose logs video_teste --tail=100
    docker compose logs mediamtx --tail=120
    throw "O stream de teste nao pode ser lido pelo MediaMTX."
}

Write-Host "[OK] Publish e read do MediaMTX confirmados." -ForegroundColor Green

Write-Host "[6/9] Reprovisionando todas as cameras..." -ForegroundColor Cyan

$ProvisionCodigo = @'
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

$ProvisionOutput = $ProvisionCodigo | docker compose exec -T api python -
$ProvisionOutput | ForEach-Object { Write-Host $_ }

if ($ProvisionOutput -match "Provisionado:\s+False") {
    throw "Uma ou mais cameras nao foram provisionadas."
}

Write-Host "[7/9] Forcando a abertura do stream da camera..." -ForegroundColor Cyan

$TriggerCodigo = @'
from app.application import SessionLocal, Camera
import subprocess

db = SessionLocal()

try:
    cameras = db.query(Camera).order_by(Camera.id.asc()).all()

    for camera in cameras:
        stream = camera.stream_name

        if not stream:
            print("Camera sem stream:", camera.id, camera.name)
            continue

        print("")
        print("Camera ID:", camera.id)
        print("Nome:", camera.name)
        print("Stream:", stream)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", f"rtsp://mediamtx:8554/{stream}",
            "-frames:v", "1",
            "-f", "null",
            "-"
        ]

        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            print("Retorno:", p.returncode)

            if p.stderr:
                print("Detalhe:", p.stderr[-1500:])

        except subprocess.TimeoutExpired:
            print("Retorno: TIMEOUT")
            print("Detalhe: o MediaMTX nao recebeu o primeiro quadro em 30 segundos.")

finally:
    db.close()
'@

$TriggerOutput = $TriggerCodigo | docker compose exec -T api python -
$TriggerOutput | ForEach-Object { Write-Host $_ }

Write-Host "[8/9] Consultando o estado dos caminhos..." -ForegroundColor Cyan
$Paths = Invoke-RestMethod `
    -Uri "http://localhost:19997/v3/paths/list" `
    -TimeoutSec 20

$Paths | ConvertTo-Json -Depth 12

$CameraPaths = @($Paths.items | Where-Object { $_.name -ne "teste" })
$ReadyPaths = @($CameraPaths | Where-Object { $_.ready -eq $true })

if ($CameraPaths.Count -gt 0 -and $ReadyPaths.Count -eq 0) {
    Write-Host ""
    Write-Host "[AVISO] A permissao do MediaMTX foi corrigida, mas a camera ainda nao entregou video." -ForegroundColor Yellow
    Write-Host "Veja o detalhe do FFmpeg acima. Normalmente ele indicara senha RTSP, codec ou timeout." -ForegroundColor Yellow
}

Write-Host "[9/9] Logs finais..." -ForegroundColor Cyan
docker compose logs mediamtx --tail=180

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " CORRECAO E DIAGNOSTICO CONCLUIDOS" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Monitoramento:" -ForegroundColor White
Write-Host "http://localhost:5177/#/monitor" -ForegroundColor Yellow
Write-Host ""
Write-Host "Depois pressione Ctrl + Shift + R." -ForegroundColor White
