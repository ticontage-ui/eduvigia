[CmdletBinding()]
param(
    [string]$ProjectPath,
    [string]$BackupRoot,
    [int]$RetentionDays = 30
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Get-Project {
    param([string]$Requested)
    $items = @(
        $Requested,
        (Join-Path $env:USERPROFILE "Documents\eduvigia"),
        (Join-Path $env:USERPROFILE "OneDrive\Documentos\eduvigia"),
        (Join-Path $env:USERPROFILE "OneDrive\Documents\eduvigia")
    ) | Where-Object { $_ }
    foreach ($item in $items) {
        if (Test-Path (Join-Path $item "docker-compose.yml")) { return (Resolve-Path $item).Path }
    }
    throw "Projeto EduVigIA não localizado."
}

function Get-EnvValue {
    param([string]$Path, [string]$Key)
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match ('^\s*' + [regex]::Escape($Key) + '\s*=\s*(.*)$')) { return $Matches[1].Trim() }
    }
    return $null
}

$Project = Get-Project $ProjectPath
$EnvPath = Join-Path $Project ".env"
if (-not (Test-Path $EnvPath)) { throw "Arquivo .env ausente." }
if (-not $BackupRoot) { $BackupRoot = Join-Path $env:USERPROFILE "Documents\EduVigIA-Backups" }
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Destination = Join-Path $BackupRoot ("EDUVIGIA-BACKUP-2.0.0-F7-R2-{0}" -f $Timestamp)
New-Item -ItemType Directory -Path $Destination -Force | Out-Null

$PostgresUser = Get-EnvValue $EnvPath "POSTGRES_USER"
$PostgresDb = Get-EnvValue $EnvPath "POSTGRES_DB"
if ($PostgresUser -notmatch '^[A-Za-z0-9_]+$' -or $PostgresDb -notmatch '^[A-Za-z0-9_]+$') {
    throw "POSTGRES_USER ou POSTGRES_DB inválido."
}

Push-Location $Project
try {
    Write-Host "[1/6] Validando PostgreSQL..." -ForegroundColor Cyan
    docker compose up -d postgres | Out-Host
    $Container = (& docker compose ps -q postgres).Trim()
    if (-not $Container) { throw "Container PostgreSQL não localizado." }

    $RemoteDump = "/tmp/eduvigia-backup-$Timestamp.dump"
    docker exec $Container pg_dump -U $PostgresUser -d $PostgresDb -Fc -f $RemoteDump | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou." }

    Write-Host "[2/6] Copiando e validando dump..." -ForegroundColor Cyan
    $DumpPath = Join-Path $Destination "database.dump"
    docker cp ("{0}:{1}" -f $Container, $RemoteDump) $DumpPath | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "docker cp do dump falhou." }
    docker exec $Container pg_restore -l $RemoteDump | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pg_restore não reconheceu o dump." }
    docker exec $Container rm -f $RemoteDump | Out-Null

    Write-Host "[3/6] Copiando dados e configurações..." -ForegroundColor Cyan
    foreach ($item in @("docker-compose.yml", "docker-compose.prod.yml", "VERSION.txt", "README.md")) {
        $source = Join-Path $Project $item
        if (Test-Path $source) { Copy-Item -LiteralPath $source -Destination $Destination -Force }
    }
    foreach ($directory in @("data", "mediamtx", "prometheus")) {
        $source = Join-Path $Project $directory
        if (Test-Path $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $Destination $directory) -Recurse -Force }
    }

    Write-Host "[4/6] Gerando inventário e hashes..." -ForegroundColor Cyan
    $Inventory = @(
        "version=2.0.0-F7-R2",
        "created_at=$((Get-Date).ToString('o'))",
        "project=$Project",
        "postgres_db=$PostgresDb"
    )
    [System.IO.File]::WriteAllLines((Join-Path $Destination "BACKUP-INFO.txt"), $Inventory, $Utf8NoBom)
    $Hashes = Get-ChildItem -LiteralPath $Destination -File -Recurse | Where-Object { $_.Name -ne "SHA256SUMS.txt" } | ForEach-Object {
        $relative = $_.FullName.Substring($Destination.Length).TrimStart('\')
        "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash, $relative
    }
    [System.IO.File]::WriteAllLines((Join-Path $Destination "SHA256SUMS.txt"), $Hashes, $Utf8NoBom)

    Write-Host "[5/6] Compactando backup..." -ForegroundColor Cyan
    $ZipPath = "$Destination.zip"
    Compress-Archive -Path (Join-Path $Destination "*") -DestinationPath $ZipPath -Force

    Write-Host "[6/6] Aplicando retenção de $RetentionDays dias..." -ForegroundColor Cyan
    $Limit = (Get-Date).AddDays(-[Math]::Max(1, $RetentionDays))
    Get-ChildItem -LiteralPath $BackupRoot -ErrorAction SilentlyContinue | Where-Object {
        $_.LastWriteTime -lt $Limit -and $_.Name -like "EDUVIGIA-BACKUP-*"
    } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "BACKUP_EDUVIGIA_OK" -ForegroundColor Green
    Write-Host ("Diretório: {0}" -f $Destination)
    Write-Host ("ZIP:       {0}" -f $ZipPath)
} finally {
    Pop-Location
}
