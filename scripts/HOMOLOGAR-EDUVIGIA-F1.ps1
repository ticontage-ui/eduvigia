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
Write-Host " EduVigIA 2.0.0-F1-R1-HF2 - Homologacao F1" -ForegroundColor Cyan
Write-Host " Escola / Secretaria / Guarda + Permissoes" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$Version = (Get-Content (Join-Path $Project "VERSION.txt") -Raw).Trim()
if ($Version -eq "2.0.0-F1-R1-HF2") { Pass "VERSION" } else { Fail "VERSION" $Version }

try { docker compose config | Out-Null; Pass "COMPOSE_DEV_CONFIG" } catch { Fail "COMPOSE_DEV_CONFIG" $_.Exception.Message }
try { docker compose -f docker-compose.prod.yml config | Out-Null; Pass "COMPOSE_PROD_CONFIG" } catch { Fail "COMPOSE_PROD_CONFIG" $_.Exception.Message }

try {
    & (Join-Path $Project "scripts\VALIDAR-EDUVIGIA.ps1")
    Pass "RUNTIME_ENDPOINTS"
} catch { Fail "RUNTIME_ENDPOINTS" $_.Exception.Message }

try {
    $Head = ((& docker compose exec -T api alembic current) -join " ").Trim()
    if ($Head -match '20260908_201_f1') { Pass "ALEMBIC_F1_HEAD" } else { Fail "ALEMBIC_F1_HEAD" $Head }
} catch { Fail "ALEMBIC_F1_HEAD" $_.Exception.Message }

try {
    $Contract = & docker compose exec -T api python -c "from app.application import ROLE_PROFILES,SCHOOL_REQUIRED_ROLES,role_permissions; required={'ADMIN_SECRETARIA','GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA','GESTOR_ESCOLA','OPERADOR_ESCOLA','TECNICO'}; ok=set(ROLE_PROFILES)==required and {'GESTOR_ESCOLA','OPERADOR_ESCOLA'}.issubset(SCHOOL_REQUIRED_ROLES) and 'command:view' in role_permissions('OPERADOR_GUARDA') and 'cameras:write' not in role_permissions('OPERADOR_GUARDA') and 'schools:write' in role_permissions('GESTOR_SECRETARIA') and 'monitor:view' in role_permissions('GESTOR_ESCOLA'); print('OK' if ok else 'FAIL')"
    if (($Contract -join '').Trim() -eq 'OK') { Pass "BACKEND_F1_ROLE_CONTRACT" } else { Fail "BACKEND_F1_ROLE_CONTRACT" ($Contract -join ' ') }
} catch { Fail "BACKEND_F1_ROLE_CONTRACT" $_.Exception.Message }

try {
    $DbContract = & docker compose exec -T api python -c "import os; from sqlalchemy import create_engine,text; e=create_engine(os.environ['DATABASE_URL']); allowed={'ADMIN_SECRETARIA','GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA','GESTOR_ESCOLA','OPERADOR_ESCOLA','TECNICO'}; legacy={'ADMIN','SUPERVISOR','OPERADOR','DESPACHANTE','ESCOLA','GESTAO'}; rows=[]; c=e.connect(); rows=c.execute(text('SELECT role, school_id FROM user_accounts')).fetchall(); c.close(); bad=[r for r,s in rows if r not in allowed or r in legacy]; missing=[(r,s) for r,s in rows if r in {'GESTOR_ESCOLA','OPERADOR_ESCOLA'} and s is None]; global_bound=[(r,s) for r,s in rows if r in {'ADMIN_SECRETARIA','GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA'} and s is not None]; print('OK' if not bad and not missing and not global_bound else 'FAIL:'+repr({'bad':bad,'missing':missing,'global_bound':global_bound}))"
    if (($DbContract -join '').Trim() -eq 'OK') { Pass "DATABASE_F1_ROLE_CONTRACT" } else { Fail "DATABASE_F1_ROLE_CONTRACT" ($DbContract -join ' ') }
} catch { Fail "DATABASE_F1_ROLE_CONTRACT" $_.Exception.Message }

try {
    $App = Get-Content (Join-Path $Project "frontend\src\app\App.jsx") -Raw
    $Required = @('ADMIN_SECRETARIA','GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA','GESTOR_ESCOLA','OPERADOR_ESCOLA','command:view')
    $Missing = @($Required | Where-Object { $App -notmatch [regex]::Escape($_) })
    $LegacyOptions = @('value="ADMIN"','value="SUPERVISOR"','value="OPERADOR"','value="DESPACHANTE"','value="ESCOLA"','value="GESTAO"') | Where-Object { $App -match [regex]::Escape($_) }
    if ($Missing.Count -eq 0 -and $LegacyOptions.Count -eq 0) { Pass "FRONTEND_F1_ROLE_CONTRACT" }
    else { Fail "FRONTEND_F1_ROLE_CONTRACT" ("missing={0}; legacy={1}" -f ($Missing -join ','), ($LegacyOptions -join ',')) }
} catch { Fail "FRONTEND_F1_ROLE_CONTRACT" $_.Exception.Message }

try {
    $LegacyRuntime = & docker compose exec -T api python -c "from app.application import canonical_role; print('OK' if canonical_role('ADMIN')=='ADMIN_SECRETARIA' and canonical_role('ESCOLA',1)=='GESTOR_ESCOLA' and canonical_role('OPERADOR',1)=='OPERADOR_ESCOLA' and canonical_role('OPERADOR',None)=='OPERADOR_GUARDA' else 'FAIL')"
    if (($LegacyRuntime -join '').Trim() -eq 'OK') { Pass "LEGACY_ROLE_COMPATIBILITY" } else { Fail "LEGACY_ROLE_COMPATIBILITY" ($LegacyRuntime -join ' ') }
} catch { Fail "LEGACY_ROLE_COMPATIBILITY" $_.Exception.Message }

if ($Failed -gt 0) {
    Write-Host ("EDUVIGIA_F1_ACCESS=REJECTED|FAILURES={0}" -f $Failed) -ForegroundColor Red
    exit 1
}

Write-Host "EDUVIGIA_F1_ACCESS=APPROVED" -ForegroundColor Green
