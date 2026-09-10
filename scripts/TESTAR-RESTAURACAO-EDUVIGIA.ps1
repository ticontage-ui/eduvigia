[CmdletBinding()]
param(
    [string]$BackupPath,
    [string]$ProjectPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Get-Project {
    param([string]$Requested)
    foreach ($item in @($Requested, (Join-Path $env:USERPROFILE "Documents\eduvigia"), (Join-Path $env:USERPROFILE "OneDrive\Documentos\eduvigia"), (Join-Path $env:USERPROFILE "OneDrive\Documents\eduvigia"))) {
        if ($item -and (Test-Path (Join-Path $item "docker-compose.yml"))) { return (Resolve-Path $item).Path }
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
if (-not $BackupPath) {
    $Root = Join-Path $env:USERPROFILE "Documents\EduVigIA-Backups"
    $BackupPath = Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "database.dump") } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $BackupPath -or -not (Test-Path $BackupPath)) { throw "Backup não localizado." }
$Temp = $null
if ([System.IO.Path]::GetExtension($BackupPath) -eq ".zip") {
    $Temp = Join-Path $env:TEMP ("eduvigia-restore-check-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $Temp -Force | Out-Null
    Expand-Archive -LiteralPath $BackupPath -DestinationPath $Temp -Force
    $BackupPath = $Temp
}
$DumpPath = Join-Path $BackupPath "database.dump"
if (-not (Test-Path $DumpPath)) { throw "database.dump ausente no backup." }

$EnvPath = Join-Path $Project ".env"
$User = Get-EnvValue $EnvPath "POSTGRES_USER"
$MainDb = Get-EnvValue $EnvPath "POSTGRES_DB"
$TestDb = "eduvigia_restore_" + (Get-Date -Format "yyyyMMddHHmmss")
$Container = ""

Push-Location $Project
try {
    docker compose up -d postgres | Out-Host
    $Container = (& docker compose ps -q postgres).Trim()
    if (-not $Container) { throw "Container PostgreSQL não localizado." }
    $RemoteDump = "/tmp/restore-validation.dump"
    docker cp $DumpPath ("{0}:{1}" -f $Container, $RemoteDump) | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Falha ao copiar dump." }
    docker exec $Container dropdb -U $User --if-exists $TestDb | Out-Null
    docker exec $Container createdb -U $User $TestDb | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar banco isolado." }
    docker exec $Container pg_restore -U $User -d $TestDb --no-owner --no-privileges --exit-on-error $RemoteDump | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Restauração isolada falhou." }
    $TableCount = (& docker exec $Container psql -U $User -d $TestDb -Atqc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';").Trim()
    if ([int]$TableCount -lt 10) { throw ("Quantidade de tabelas restauradas insuficiente: {0}" -f $TableCount) }
    Write-Host ("RESTORE_ISOLATED_OK tables={0}" -f $TableCount) -ForegroundColor Green
} finally {
    if ($Container) {
        docker exec $Container dropdb -U $User --if-exists $TestDb | Out-Null
        docker exec $Container rm -f /tmp/restore-validation.dump | Out-Null
    }
    Pop-Location
    if ($Temp -and (Test-Path $Temp)) { Remove-Item -LiteralPath $Temp -Recurse -Force }
}
