[CmdletBinding()]
param([string]$ProjectPath = "$env:USERPROFILE\Documents\eduvigia")

$ErrorActionPreference = "Stop"
$Failed = 0
function Pass([string]$Name) { Write-Host ("PASS|{0}" -f $Name) -ForegroundColor Green }
function Fail([string]$Name, [string]$Detail = "") {
    $script:Failed++
    if ($Detail) { Write-Host ("FAIL|{0}|{1}" -f $Name, $Detail) -ForegroundColor Red }
    else { Write-Host ("FAIL|{0}" -f $Name) -ForegroundColor Red }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " EduVigIA 2.0.0-F2-R1-HF3 - Homologacao F2" -ForegroundColor Cyan
Write-Host " VMS Basico - NVR + MAIN/SUB + Mosaico + Favoritos" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $ProjectPath "docker-compose.yml"))) { throw "Projeto não localizado: $ProjectPath" }
Push-Location $ProjectPath
try {
    $Version = (Get-Content (Join-Path $ProjectPath "VERSION.txt") -Raw).Trim()
    if ($Version -eq "2.0.0-F2-R1-HF3") { Pass "VERSION" } else { Fail "VERSION" $Version }

    try { docker compose config | Out-Null; Pass "COMPOSE_DEV_CONFIG" } catch { Fail "COMPOSE_DEV_CONFIG" $_.Exception.Message }
    try { docker compose -f docker-compose.prod.yml config | Out-Null; Pass "COMPOSE_PROD_CONFIG" } catch { Fail "COMPOSE_PROD_CONFIG" $_.Exception.Message }

    try {
        & (Join-Path $ProjectPath "scripts\VALIDAR-EDUVIGIA.ps1")
        Pass "RUNTIME_ENDPOINTS"
    } catch { Fail "RUNTIME_ENDPOINTS" $_.Exception.Message }

    try {
        $Head = ((& docker compose exec -T api alembic current) -join " ").Trim()
        if ($Head -match '20260908_202_f2') { Pass "ALEMBIC_F2_HEAD" } else { Fail "ALEMBIC_F2_HEAD" $Head }
    } catch { Fail "ALEMBIC_F2_HEAD" $_.Exception.Message }

    try {
        $Preflight = (& docker compose exec -T api python -m app.vms_f2_preflight) -join ""
        if ($Preflight -match 'EDUVIGIA_F2_VMS_PREFLIGHT_OK') { Pass "BACKEND_F2_VMS_CONTRACT" }
        else { Fail "BACKEND_F2_VMS_CONTRACT" $Preflight }
    } catch { Fail "BACKEND_F2_VMS_CONTRACT" $_.Exception.Message }

    try {
        $DbContract = (& docker compose exec -T api python -c "import os; from sqlalchemy import create_engine,inspect,text; e=create_engine(os.environ['DATABASE_URL']); i=inspect(e); cols={c['name'] for c in i.get_columns('cameras')}; req={'rtsp_url_main','rtsp_url_sub','main_status','sub_status','main_codec','main_resolution','main_fps','main_bitrate_kbps','sub_codec','sub_resolution','sub_fps','sub_bitrate_kbps','stream_name_main','stream_name_sub'}; fav=i.has_table('camera_favorites'); c=e.connect(); v=c.execute(text('select version_num from alembic_version')).scalar(); c.close(); print('OK' if req.issubset(cols) and fav and v=='20260908_202_f2' else 'FAIL:'+repr({'missing':sorted(req-cols),'favorites':fav,'version':v}))") -join ""
        if ($DbContract.Trim() -eq 'OK') { Pass "DATABASE_F2_VMS_CONTRACT" } else { Fail "DATABASE_F2_VMS_CONTRACT" $DbContract }
    } catch { Fail "DATABASE_F2_VMS_CONTRACT" $_.Exception.Message }

    try {
        $SecurityContract = (& docker compose exec -T api python -c "from app.application import CameraOut; names=['rtsp_url','rtsp_url_main','rtsp_url_sub','rtsp_path_main','rtsp_path_sub','password']; print('OK' if all(CameraOut.model_fields[n].exclude is True for n in names) else 'FAIL')") -join ""
        if ($SecurityContract.Trim() -eq 'OK') { Pass "RTSP_SECRET_SERIALIZATION_BLOCKED" } else { Fail "RTSP_SECRET_SERIALIZATION_BLOCKED" $SecurityContract }
    } catch { Fail "RTSP_SECRET_SERIALIZATION_BLOCKED" $_.Exception.Message }

    try {
        $App = Get-Content (Join-Path $ProjectPath "frontend\src\app\App.jsx") -Raw
        $Required = @(
            'Qualidade automática',
            'MAIN — Alta qualidade',
            'SUB — Mosaico',
            'CameraMonitorTile',
            'gridSize === 1 ? "MAIN" : "SUB"',
            '/monitoring/favorites',
            '/monitoring/status-refresh',
            '<option value={1}>Grade 1</option>',
            '<option value={4}>Grade 4</option>',
            '<option value={9}>Grade 9</option>',
            '<option value={16}>Grade 16</option>'
        )
        $Missing = @($Required | Where-Object { $App -notmatch [regex]::Escape($_) })
        if ($Missing.Count -eq 0) { Pass "FRONTEND_F2_VMS_CONTRACT" }
        else { Fail "FRONTEND_F2_VMS_CONTRACT" ("missing={0}" -f ($Missing -join ',')) }
    } catch { Fail "FRONTEND_F2_VMS_CONTRACT" $_.Exception.Message }

    foreach ($Item in @(
        @{Name='WEBRTC_DEV_HTTP'; Url='http://127.0.0.1:18889/teste'},
        @{Name='HLS_DEV_HTTP'; Url='http://127.0.0.1:18888/teste/index.m3u8'}
    )) {
        try {
            $Code = (& curl.exe -sS -o NUL -w "%{http_code}" --max-time 10 $Item.Url).Trim()
            if ($Code -match '^[234][0-9][0-9]$') { Pass $Item.Name }
            else { Fail $Item.Name ("HTTP={0}" -f $Code) }
        } catch { Fail $Item.Name $_.Exception.Message }
    }

    $TestDbUrl = "sqlite:////tmp/eduvigia-f2-hf3-test.db"
    $AppVolume = "./backend/app:/app/app:ro"
    $TestVolume = "./backend/tests:/app/tests:ro"

    try {
        $ImportProbe = (& docker compose run --rm -T --no-deps `
            -e "PYTHONPATH=/app" `
            -e "DATABASE_URL=$TestDbUrl" `
            -e "APP_VERSION=2.0.0-F2-R1-HF3" `
            -e "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD=F2Test@2026!" `
            -e "EDUVIGIA_CREDENTIAL_KEY=mQvP4uC9fSMwICBE7Mum90ZeX_qhNaL8TiYf8RUMfFs=" `
            -e "EDUVIGIA_STREAM_SIGNING_KEY=f2-hf3-test-stream-key" `
            -v $AppVolume `
            -v $TestVolume `
            -w /app `
            api python -c "import app; import app.application; print('EDUVIGIA_TEST_RUNNER_IMPORT_OK')") -join "`n"
        if ($LASTEXITCODE -eq 0 -and $ImportProbe -match 'EDUVIGIA_TEST_RUNNER_IMPORT_OK') { Pass "TEST_RUNNER_APP_IMPORT" }
        else { Fail "TEST_RUNNER_APP_IMPORT" ("exit={0}; output={1}" -f $LASTEXITCODE, $ImportProbe) }
    } catch { Fail "TEST_RUNNER_APP_IMPORT" $_.Exception.Message }

    try {
        & docker compose run --rm -T --no-deps `
            -e "PYTHONPATH=/app" `
            -e "DATABASE_URL=$TestDbUrl" `
            -e "APP_VERSION=2.0.0-F2-R1-HF3" `
            -e "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD=F2Test@2026!" `
            -e "EDUVIGIA_CREDENTIAL_KEY=mQvP4uC9fSMwICBE7Mum90ZeX_qhNaL8TiYf8RUMfFs=" `
            -e "EDUVIGIA_STREAM_SIGNING_KEY=f2-hf3-test-stream-key" `
            -v $AppVolume `
            -v $TestVolume `
            -w /app `
            api python -m pytest -q /app/tests
        if ($LASTEXITCODE -eq 0) { Pass "BACKEND_REGRESSION_ISOLATED" } else { Fail "BACKEND_REGRESSION_ISOLATED" ("exit={0}" -f $LASTEXITCODE) }
    } catch { Fail "BACKEND_REGRESSION_ISOLATED" $_.Exception.Message }

    try {
        # Validação objetiva do isolamento. Não inspeciona o próprio texto do script,
        # evitando falsos negativos autorreferentes.
        $RuntimeDbUrl = ((& docker compose exec -T api python -c "import os; print(os.environ.get('DATABASE_URL',''))") -join "").Trim()
        $Isolated = (
            $TestDbUrl -eq 'sqlite:////tmp/eduvigia-f2-hf3-test.db' -and
            $RuntimeDbUrl -ne $TestDbUrl -and
            $TestDbUrl.StartsWith('sqlite:////tmp/') -and
            $AppVolume.EndsWith('/app/app:ro') -and
            $TestVolume.EndsWith('/app/tests:ro')
        )
        if ($Isolated) {
            Pass "TEST_GATE_ISOLATED_FROM_RUNTIME_DB"
        } else {
            Fail "TEST_GATE_ISOLATED_FROM_RUNTIME_DB" ("runtime_db={0}; test_db={1}; app_mount={2}; test_mount={3}" -f $RuntimeDbUrl,$TestDbUrl,$AppVolume,$TestVolume)
        }
    } catch { Fail "TEST_GATE_ISOLATED_FROM_RUNTIME_DB" $_.Exception.Message }

    try {
        $WebContainer = docker compose ps --status running --services | Where-Object { $_ -eq 'web' }
        if ($WebContainer) { Pass "WEB_BUILD_RUNTIME" } else { Fail "WEB_BUILD_RUNTIME" "container web não está em execução" }
    } catch { Fail "WEB_BUILD_RUNTIME" $_.Exception.Message }
} finally {
    Pop-Location
}

if ($Failed -gt 0) {
    Write-Host ("EDUVIGIA_F2_VMS_BASIC=REJECTED|FAILURES={0}" -f $Failed) -ForegroundColor Red
    exit 1
}
Write-Host "EDUVIGIA_F2_VMS_BASIC=APPROVED" -ForegroundColor Green
Write-Host "EDUVIGIA_F2_HF3_TEST_GATE=APPROVED" -ForegroundColor Green
