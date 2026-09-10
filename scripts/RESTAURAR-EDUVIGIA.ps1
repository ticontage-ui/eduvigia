[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [switch]$ConfirmRestore,
    [string]$ProjectPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) { throw "Restauração bloqueada. Execute novamente com -ConfirmRestore após validar o backup." }

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
if (-not (Test-Path $BackupPath)) { throw "Backup não encontrado: $BackupPath" }
$Temp = $null
if ([System.IO.Path]::GetExtension($BackupPath) -eq ".zip") {
    $Temp = Join-Path $env:TEMP ("eduvigia-restore-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $Temp -Force | Out-Null
    Expand-Archive -LiteralPath $BackupPath -DestinationPath $Temp -Force
    $BackupPath = $Temp
}
$Dump = Join-Path $BackupPath "database.dump"
if (-not (Test-Path $Dump)) { throw "database.dump ausente." }
$EnvPath = Join-Path $Project ".env"
$User = Get-EnvValue $EnvPath "POSTGRES_USER"
$Db = Get-EnvValue $EnvPath "POSTGRES_DB"

Push-Location $Project
try {
    & (Join-Path $Project "scripts\TESTAR-RESTAURACAO-EDUVIGIA.ps1") -BackupPath $BackupPath -ProjectPath $Project
    docker compose stop api web proxy prometheus video_teste mediamtx | Out-Host
    docker compose up -d postgres | Out-Host
    $Container = (& docker compose ps -q postgres).Trim()
    $RemoteDump = "/tmp/eduvigia-restore.dump"
    docker cp $Dump ("{0}:{1}" -f $Container, $RemoteDump) | Out-Host
    docker exec $Container pg_restore -U $User -d $Db --clean --if-exists --no-owner --no-privileges --exit-on-error $RemoteDump | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Restauração do PostgreSQL falhou." }
    docker exec $Container rm -f $RemoteDump | Out-Null
    $DataSource = Join-Path $BackupPath "data"
    if (Test-Path $DataSource) {
        $DataTarget = Join-Path $Project "data"
        if (Test-Path $DataTarget) { Remove-Item -LiteralPath $DataTarget -Recurse -Force }
        Copy-Item -LiteralPath $DataSource -Destination $DataTarget -Recurse -Force
    }
    docker compose up -d --build | Out-Host
    Write-Host "RESTAURACAO_EDUVIGIA_OK" -ForegroundColor Green
} finally {
    Pop-Location
    if ($Temp -and (Test-Path $Temp)) { Remove-Item -LiteralPath $Temp -Recurse -Force }
}
