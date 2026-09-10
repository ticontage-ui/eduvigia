[CmdletBinding()]
param([string]$ProjectPath)

$ErrorActionPreference = "Stop"
$Project = if ($ProjectPath) { $ProjectPath } else { Join-Path $env:USERPROFILE "Documents\eduvigia" }
if (-not (Test-Path (Join-Path $Project "docker-compose.yml"))) { throw "Projeto não localizado: $Project" }
Set-Location $Project

$Failed = 0
function Pass([string]$Name) { Write-Host ("PASS|{0}" -f $Name) -ForegroundColor Green }
function Fail([string]$Name, [string]$Detail = "") {
    $script:Failed++
    if ($Detail) { Write-Host ("FAIL|{0}|{1}" -f $Name, $Detail) -ForegroundColor Red }
    else { Write-Host ("FAIL|{0}" -f $Name) -ForegroundColor Red }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " EduVigIA 2.0.0-F0-R1 - Homologacao F0" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$Version = (Get-Content (Join-Path $Project "VERSION.txt") -Raw).Trim()
if ($Version -eq "2.0.0-F0-R1") { Pass "VERSION" } else { Fail "VERSION" $Version }

$ForbiddenPaths = @(
    "ai_engine",
    "data\ai-evidence"
)
foreach ($Relative in $ForbiddenPaths) {
    if (Test-Path (Join-Path $Project $Relative)) { Fail "LEGACY_PATH_ABSENT" $Relative }
    else { Pass ("LEGACY_PATH_ABSENT:{0}" -f $Relative) }
}

$ActiveTargets = @(
    "backend\app",
    "frontend\src",
    "frontend\index.html",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "mediamtx",
    "prometheus",
    "nginx"
)
$LegacyPattern = 'Bem-Estar|Reconhecimento Facial|emotion_analysis|biometrics|nvidia-smi|/ai/|ai_enabled|ai_event_id|AI Server|AI Engine|Integração IA'
$LegacyHits = @()
foreach ($Target in $ActiveTargets) {
    $Path = Join-Path $Project $Target
    if (Test-Path $Path) {
        $Items = if ((Get-Item $Path).PSIsContainer) { Get-ChildItem $Path -File -Recurse -ErrorAction SilentlyContinue } else { @(Get-Item $Path) }
        foreach ($Item in $Items) {
            $Matches = Select-String -Path $Item.FullName -Pattern $LegacyPattern -AllMatches -ErrorAction SilentlyContinue
            if ($Matches) { $LegacyHits += $Matches }
        }
    }
}
if ($LegacyHits.Count -eq 0) { Pass "ACTIVE_LEGACY_SCOPE_REMOVED" }
else {
    Fail "ACTIVE_LEGACY_SCOPE_REMOVED" ("{0} ocorrencia(s)" -f $LegacyHits.Count)
    $LegacyHits | Select-Object -First 20 | ForEach-Object { Write-Host ("  {0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()) }
}

$PrivateFiles = Get-ChildItem $Project -File -Recurse -ErrorAction SilentlyContinue | Where-Object {
    $_.FullName -notmatch '\\documentacao\\archive\\' -and ($_.Name -eq '.env' -or $_.Extension -in @('.key','.pem'))
}
# Um .env local e certificados gerados em runtime são esperados após instalação;
# a regra de release é validada pelo pacote distribuído, não pelo host implantado.
$ReleasePrivate = $PrivateFiles | Where-Object { $_.FullName -notmatch '\\nginx\\certs\\' -and $_.Name -ne '.env' }
if ($ReleasePrivate.Count -eq 0) { Pass "NO_UNEXPECTED_PRIVATE_FILES" } else { Fail "NO_UNEXPECTED_PRIVATE_FILES" ($ReleasePrivate.FullName -join ', ') }

try { docker compose config | Out-Null; Pass "COMPOSE_DEV_CONFIG" } catch { Fail "COMPOSE_DEV_CONFIG" $_.Exception.Message }
try { docker compose -f docker-compose.prod.yml config | Out-Null; Pass "COMPOSE_PROD_CONFIG" } catch { Fail "COMPOSE_PROD_CONFIG" $_.Exception.Message }

try {
    $Services = (& docker compose config --services) -join ','
    if ($Services -match 'ai_engine|ai-engine') { Fail "AI_SERVICE_ABSENT" $Services } else { Pass "AI_SERVICE_ABSENT" }
} catch { Fail "AI_SERVICE_ABSENT" $_.Exception.Message }

try {
    & (Join-Path $Project "scripts\VALIDAR-EDUVIGIA.ps1")
    Pass "RUNTIME_ENDPOINTS"
} catch { Fail "RUNTIME_ENDPOINTS" $_.Exception.Message }

try {
    $Contract = & docker compose exec -T api python -c "from app.application import app, Base, Camera, Alert; r=[getattr(x,'path','') for x in app.routes]; print('OK' if not [x for x in r if x.startswith('/ai') or x.startswith('/internal/ai')] and not [t for t in Base.metadata.tables if t.startswith('ai_')] and not hasattr(Camera,'ai_enabled') and not hasattr(Alert,'ai_event_id') and '/reports/summary' in r else 'FAIL')"
    if (($Contract -join '').Trim() -eq 'OK') { Pass "BACKEND_F0_CONTRACT" } else { Fail "BACKEND_F0_CONTRACT" ($Contract -join ' ') }
} catch { Fail "BACKEND_F0_CONTRACT" $_.Exception.Message }

try {
    $DbContract = & docker compose exec -T api python -c "import os; from sqlalchemy import create_engine, inspect; i=inspect(create_engine(os.environ['DATABASE_URL'])); bad=[t for t in ['ai_servers','ai_rules','ai_events','ai_telemetry'] if i.has_table(t)]; ac=i.get_columns('alerts') if i.has_table('alerts') else []; cc=i.get_columns('cameras') if i.has_table('cameras') else []; badc=[c['name'] for c in ac if c['name']=='ai_event_id']+[c['name'] for c in cc if c['name']=='ai_enabled']; print('OK' if not bad and not badc else 'FAIL:'+','.join(bad+badc))"
    if (($DbContract -join '').Trim() -eq 'OK') { Pass "DATABASE_F0_CONTRACT" } else { Fail "DATABASE_F0_CONTRACT" ($DbContract -join ' ') }
} catch { Fail "DATABASE_F0_CONTRACT" $_.Exception.Message }

if ($Failed -gt 0) {
    Write-Host ("EDUVIGIA_F0_CLEAR=REJECTED|FAILURES={0}" -f $Failed) -ForegroundColor Red
    exit 1
}

Write-Host "EDUVIGIA_F0_CLEAR=APPROVED" -ForegroundColor Green
