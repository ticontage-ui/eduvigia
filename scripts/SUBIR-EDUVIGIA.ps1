[CmdletBinding()]
param([string]$ProjectPath)

$ErrorActionPreference = "Stop"
$Project = if ($ProjectPath) { $ProjectPath } else { Join-Path $env:USERPROFILE "Documents\eduvigia" }
if (-not (Test-Path (Join-Path $Project "docker-compose.yml"))) { throw "Projeto não localizado: $Project" }
if (-not (Test-Path (Join-Path $Project ".env"))) { throw "Arquivo .env não localizado. Crie-o a partir de .env.example e configure os secrets antes de subir a stack." }

Set-Location $Project

# Windows PowerShell 5.1 pode converter stderr informativo de executáveis nativos
# em NativeCommandError quando ErrorActionPreference=Stop. Docker Compose usa stderr
# para mensagens não fatais, por exemplo "Container ... Creating". Os wrappers abaixo
# sempre decidem sucesso/falha pelo exit code real do docker.exe.
function Invoke-DockerPassthrough {
    param([string[]]$Arguments)
    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Output = @(& docker @Arguments 2>&1)
        $Code = $LASTEXITCODE
        foreach ($Line in $Output) {
            if ($null -ne $Line) { Write-Host ([string]$Line) }
        }
        return $Code
    } finally {
        $ErrorActionPreference = $PreviousPreference
    }
}

function Invoke-DockerProbe {
    param([string[]]$Arguments)
    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & docker @Arguments 2>$null | Out-Null
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousPreference
    }
}

function Invoke-DockerCapture {
    param([string[]]$Arguments)
    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Output = @(& docker @Arguments 2>$null)
        $Code = $LASTEXITCODE
        return [PSCustomObject]@{ ExitCode = $Code; Output = $Output }
    } finally {
        $ErrorActionPreference = $PreviousPreference
    }
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$DefaultValue = ""
    )
    $Line = Get-Content $Path | Where-Object { $_ -match ("^" + [regex]::Escape($Name) + "=") } | Select-Object -Last 1
    if (-not $Line) { return $DefaultValue }
    $Value = ($Line -replace ("^" + [regex]::Escape($Name) + "="), "").Trim()
    if (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or ($Value.StartsWith("'") -and $Value.EndsWith("'"))) {
        if ($Value.Length -ge 2) { $Value = $Value.Substring(1, $Value.Length - 2) }
    }
    return $Value
}

Write-Host "[1/8] Build API + Web..." -ForegroundColor Cyan
docker compose build api web
if ($LASTEXITCODE -ne 0) { throw "Falha no build dos serviços." }

Write-Host "[2/8] Gerando/validando certificado TLS local com ambiente minimo..." -ForegroundColor Cyan
$ApiImage = "eduvigia-api:latest"
$ImageInspect = Invoke-DockerProbe -Arguments @("image", "inspect", $ApiImage)
if ($ImageInspect -ne 0) { throw "Imagem determinística da API não localizada após o build: $ApiImage" }
Write-Host "PASS|API_IMAGE_DETERMINISTIC" -ForegroundColor Green

$TlsHosts = Get-DotEnvValue -Path (Join-Path $Project ".env") -Name "EDUVIGIA_TLS_HOSTS" -DefaultValue "localhost,127.0.0.1"
if ([string]::IsNullOrWhiteSpace($TlsHosts)) { $TlsHosts = "localhost,127.0.0.1" }
if ($TlsHosts.Length -gt 2048) { throw "EDUVIGIA_TLS_HOSTS excede o limite seguro de 2048 caracteres." }

$CertHostPath = (Resolve-Path (Join-Path $Project "nginx\certs")).Path
$CertVolume = "${CertHostPath}:/certs"
$CertExit = Invoke-DockerPassthrough -Arguments @(
    "run", "--rm",
    "-v", $CertVolume,
    "-e", "EDUVIGIA_TLS_HOSTS=$TlsHosts",
    "-e", "EDUVIGIA_TLS_CERT_DIR=/certs",
    $ApiImage,
    "python", "-m", "app.certgen"
)
if ($CertExit -ne 0) { throw "Falha na geração do certificado TLS em ambiente mínimo. exit=$CertExit" }
Write-Host "PASS|TLS_CERT_MINIMAL_DOCKER_RUN" -ForegroundColor Green
Write-Host "PASS|TLS_CERT_DOCKER_RUN_PS51_SAFE" -ForegroundColor Green

Write-Host "[3/8] Subindo dependências sem iniciar a API..." -ForegroundColor Cyan
docker compose up -d postgres redis mediamtx
if ($LASTEXITCODE -ne 0) { throw "Falha ao subir dependências." }

$DatabaseUrl = Get-DotEnvValue -Path (Join-Path $Project ".env") -Name "DATABASE_URL"
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "DATABASE_URL não localizada no .env." }
if ($DatabaseUrl.Length -gt 8192) { throw "DATABASE_URL excede o limite seguro de 8192 caracteres." }

$NetworkResult = Invoke-DockerCapture -Arguments @("inspect", "-f", '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}', "eduvigia_postgres")
if ($NetworkResult.ExitCode -ne 0) { throw "Não foi possível identificar a rede Docker do PostgreSQL. exit=$($NetworkResult.ExitCode)" }
$DockerNetwork = (($NetworkResult.Output | Select-Object -Last 1) -as [string]).Trim()
if (-not $DockerNetwork) { throw "Rede Docker do PostgreSQL não identificada." }

Write-Host "[4/8] Aguardando PostgreSQL ficar disponível com runner mínimo..." -ForegroundColor Cyan
$DbReady = $false
$DbProbe = "import os; from sqlalchemy import create_engine,text; e=create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True); c=e.connect(); c.execute(text('SELECT 1')); c.close(); print('DB_OK')"
for ($i = 0; $i -lt 36; $i++) {
    $ProbeExit = Invoke-DockerProbe -Arguments @(
        "run", "--rm", "--network", $DockerNetwork,
        "-e", "DATABASE_URL=$DatabaseUrl",
        $ApiImage,
        "python", "-c", $DbProbe
    )
    if ($ProbeExit -eq 0) { $DbReady = $true; break }
    Start-Sleep -Seconds 5
}
if (-not $DbReady) {
    docker compose ps | Out-Host
    throw "PostgreSQL não ficou disponível no período de validação."
}
Write-Host "PASS|DATABASE_READY_BEFORE_MIGRATION" -ForegroundColor Green
Write-Host "PASS|DB_PROBE_MINIMAL_DOCKER_RUN" -ForegroundColor Green

Write-Host "[5/8] Aplicando migrations antes do primeiro boot da API com runner mínimo..." -ForegroundColor Cyan
$AlembicProbe = "import os; from sqlalchemy import create_engine, inspect; e=create_engine(os.environ['DATABASE_URL']); print('YES' if inspect(e).has_table('alembic_version') else 'NO')"
$AlembicResult = Invoke-DockerCapture -Arguments @(
    "run", "--rm", "--network", $DockerNetwork,
    "-e", "DATABASE_URL=$DatabaseUrl",
    $ApiImage,
    "python", "-c", $AlembicProbe
)
if ($AlembicResult.ExitCode -ne 0) { throw "Não foi possível verificar o estado do Alembic. exit=$($AlembicResult.ExitCode)" }
$HasAlembic = (($AlembicResult.Output | Select-Object -Last 1) -as [string]).Trim()
if ($HasAlembic -notin @("YES", "NO")) { throw "Resposta Alembic inválida: $HasAlembic" }
if ($HasAlembic -eq "NO") {
    $StampExit = Invoke-DockerPassthrough -Arguments @(
        "run", "--rm", "--network", $DockerNetwork,
        "-e", "DATABASE_URL=$DatabaseUrl",
        $ApiImage,
        "alembic", "stamp", "20260625_130"
    )
    if ($StampExit -ne 0) { throw "Falha ao marcar a baseline Alembic legada. exit=$StampExit" }
}
$UpgradeExit = Invoke-DockerPassthrough -Arguments @(
    "run", "--rm", "--network", $DockerNetwork,
    "-e", "DATABASE_URL=$DatabaseUrl",
    $ApiImage,
    "alembic", "upgrade", "head"
)
if ($UpgradeExit -ne 0) { throw "Falha ao aplicar migrations antes do boot da API. exit=$UpgradeExit" }
Write-Host "PASS|MIGRATION_BEFORE_API_BOOT" -ForegroundColor Green
Write-Host "PASS|ALEMBIC_MINIMAL_DOCKER_RUN" -ForegroundColor Green
Write-Host "PASS|ALL_BOOTSTRAP_DOCKER_RUN_MINIMAL_ENV" -ForegroundColor Green
Write-Host "PASS|ALL_BOOTSTRAP_DOCKER_RUN_PS51_SAFE" -ForegroundColor Green

Write-Host "[6/8] Subindo API já com schema atualizado..." -ForegroundColor Cyan
docker compose up -d api
if ($LASTEXITCODE -ne 0) { throw "Falha ao subir API após migrations." }

Write-Host "[7/8] Aguardando API ficar saudável..." -ForegroundColor Cyan
$Ready = $false
for ($i = 0; $i -lt 36; $i++) {
    try {
        $Response = Invoke-WebRequest -Uri "http://127.0.0.1:8002/health" -UseBasicParsing -TimeoutSec 5
        if ($Response.StatusCode -eq 200) { $Ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 5
}
if (-not $Ready) {
    docker compose ps | Out-Host
    docker compose logs --tail 120 api | Out-Host
    throw "API não ficou saudável após validar o schema F6."
}
Write-Host "PASS|API_HEALTH_AFTER_MIGRATION" -ForegroundColor Green

Write-Host "[8/8] Subindo stack completa e exibindo estado..." -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "Falha ao subir a stack completa." }
docker compose ps | Out-Host

Write-Host ""
Write-Host "Painel direto:  http://localhost:5177" -ForegroundColor Green
Write-Host "Proxy HTTP:     http://localhost:8088 (redireciona para HTTPS)" -ForegroundColor Green
Write-Host "Proxy HTTPS:    https://localhost:18443" -ForegroundColor Green
Write-Host "API:            http://localhost:8002/docs" -ForegroundColor Green
Write-Host "Prometheus:     http://localhost:19090" -ForegroundColor Green
Write-Host "WebRTC DEV:     http://localhost:18889" -ForegroundColor Green
Write-Host "HLS DEV:        http://localhost:18888" -ForegroundColor Green
Write-Host "SUBIR_EDUVIGIA_2.0.0_F7_R1_OK" -ForegroundColor Green
