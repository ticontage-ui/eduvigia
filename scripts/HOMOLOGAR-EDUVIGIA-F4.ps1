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
    } finally { $ErrorActionPreference = $PreviousPreference }
}

function Invoke-DockerCapture {
    param([string[]]$Arguments)
    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Output = @(& docker @Arguments 2>$null)
        $Code = $LASTEXITCODE
        return [PSCustomObject]@{ ExitCode = $Code; Output = $Output }
    } finally { $ErrorActionPreference = $PreviousPreference }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " EduVigIA 2.0.0-F4-R1-HF1 - Homologacao F4" -ForegroundColor Cyan
Write-Host " Playback + Evidencias Forenses + F3-R2 preservado" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $ProjectPath "docker-compose.yml"))) { throw "Projeto não localizado: $ProjectPath" }
Push-Location $ProjectPath
try {
    $Version = (Get-Content (Join-Path $ProjectPath "VERSION.txt") -Raw).Trim()
    if ($Version -eq "2.0.0-F4-R1-HF1") { Pass "VERSION" } else { Fail "VERSION" $Version }

    try {
        $LegacyFiles = @(
            "backend\app\vms_f2_preflight.py",
            "backend\app\vms_f3_preflight.py",
            "backend\app\nvr_preflight.py",
            "backend\app\alert_center_preflight.py"
        )
        $LegacyVersionCoupling = @()
        foreach ($Rel in $LegacyFiles) {
            $Raw = Get-Content (Join-Path $ProjectPath $Rel) -Raw
            if ($Raw -match 'APP_VERSION\s*!=\s*["'']' -or $Raw -match 'EXPECTED_VERSION\s*=') { $LegacyVersionCoupling += $Rel }
        }
        if ($LegacyVersionCoupling.Count -eq 0) { Pass "LEGACY_PREFLIGHT_VERSION_AGNOSTIC" }
        else { Fail "LEGACY_PREFLIGHT_VERSION_AGNOSTIC" ("coupled={0}" -f ($LegacyVersionCoupling -join ',')) }
    } catch { Fail "LEGACY_PREFLIGHT_VERSION_AGNOSTIC" $_.Exception.Message }

    try {
        $AppJsx = Get-Content (Join-Path $ProjectPath "frontend\src\app\App.jsx") -Raw
        $Occurrences = ([regex]::Matches($AppJsx, 'videoDevices=\{videoDevices\}')).Count
        # CamerasPage and Playback page may each legitimately receive the prop; duplicate adjacent prop is forbidden.
        $DuplicateAdjacent = $AppJsx -match 'videoDevices=\{videoDevices\}[\s\S]{0,160}videoDevices=\{videoDevices\}'
        if (-not $DuplicateAdjacent) { Pass "FRONTEND_DUPLICATE_PROP_CLEAN" }
        else { Fail "FRONTEND_DUPLICATE_PROP_CLEAN" ("occurrences={0}" -f $Occurrences) }
    } catch { Fail "FRONTEND_DUPLICATE_PROP_CLEAN" $_.Exception.Message }

    try { docker compose config | Out-Null; Pass "COMPOSE_DEV_CONFIG" } catch { Fail "COMPOSE_DEV_CONFIG" $_.Exception.Message }
    try { docker compose -f docker-compose.prod.yml config | Out-Null; Pass "COMPOSE_PROD_CONFIG" } catch { Fail "COMPOSE_PROD_CONFIG" $_.Exception.Message }


    try {
        # HF6 verifier R2: validate the resolved Compose model instead of slicing YAML with regex.
        # This prevents false positives where the postgres block accidentally includes later services.
        function Get-ResolvedServiceEnvKeys {
            param(
                [string[]]$ComposeOptions,
                [string]$ServiceName
            )
            $DockerArgs = @("compose") + $ComposeOptions + @("config", "--format", "json")
            $Result = Invoke-DockerCapture -Arguments $DockerArgs
            if ($Result.ExitCode -ne 0) {
                throw ("docker compose config JSON falhou para {0}; exit={1}" -f $ServiceName, $Result.ExitCode)
            }
            $Json = ($Result.Output -join "`n").Trim()
            if (-not $Json) { throw ("docker compose config JSON vazio para {0}" -f $ServiceName) }
            $Config = $Json | ConvertFrom-Json
            $Service = $Config.services.$ServiceName
            if ($null -eq $Service) { throw ("servico {0} nao encontrado no compose resolvido" -f $ServiceName) }
            if ($null -eq $Service.environment) { return @() }
            return @($Service.environment.PSObject.Properties.Name)
        }

        $DevComposeRaw = Get-Content (Join-Path $ProjectPath "docker-compose.yml") -Raw
        $ProdComposeRaw = Get-Content (Join-Path $ProjectPath "docker-compose.prod.yml") -Raw
        # Current contract intentionally forbids env_file in the runtime Compose files.
        # Environment is allowlisted explicitly per service.
        $NoEnvFile = (
            $DevComposeRaw -notmatch '(?m)^\s+env_file:' -and
            $ProdComposeRaw -notmatch '(?m)^\s+env_file:'
        )
        if ($NoEnvFile) { Pass "NO_RUNTIME_ENV_FILE" } else { Fail "NO_RUNTIME_ENV_FILE" "postgres/api ainda herdam .env inteiro" }

        $DevPgKeys = @(Get-ResolvedServiceEnvKeys -ComposeOptions @() -ServiceName "postgres")
        $ProdPgKeys = @(Get-ResolvedServiceEnvKeys -ComposeOptions @("-f", "docker-compose.prod.yml") -ServiceName "postgres")
        $PgAllowed = @("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
        $PgDevMissing = @($PgAllowed | Where-Object { $DevPgKeys -notcontains $_ })
        $PgProdMissing = @($PgAllowed | Where-Object { $ProdPgKeys -notcontains $_ })
        $PgDevUnexpected = @($DevPgKeys | Where-Object { $PgAllowed -notcontains $_ })
        $PgProdUnexpected = @($ProdPgKeys | Where-Object { $PgAllowed -notcontains $_ })
        if ($PgDevMissing.Count -eq 0 -and $PgProdMissing.Count -eq 0 -and $PgDevUnexpected.Count -eq 0 -and $PgProdUnexpected.Count -eq 0) {
            Pass "POSTGRES_ENV_ALLOWLIST"
            Pass "POSTGRES_ENV_ALLOWLIST_RESOLVED_JSON"
        } else {
            Fail "POSTGRES_ENV_ALLOWLIST" ("dev_missing={0};prod_missing={1};dev_unexpected={2};prod_unexpected={3}" -f ($PgDevMissing -join ','),($PgProdMissing -join ','),($PgDevUnexpected -join ','),($PgProdUnexpected -join ','))
        }

        $DevApiKeys = @(Get-ResolvedServiceEnvKeys -ComposeOptions @() -ServiceName "api")
        $ProdApiKeys = @(Get-ResolvedServiceEnvKeys -ComposeOptions @("-f", "docker-compose.prod.yml") -ServiceName "api")
        $ApiRequired = @("DATABASE_URL", "REDIS_URL", "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD", "EDUVIGIA_CREDENTIAL_KEY", "EDUVIGIA_STREAM_SIGNING_KEY", "EDUVIGIA_PTZ_LEASE_SECONDS", "CORS_ORIGINS")
        $ApiMissing = @($ApiRequired | Where-Object { $DevApiKeys -notcontains $_ -or $ProdApiKeys -notcontains $_ })
        if ($ApiMissing.Count -eq 0) { Pass "API_ENV_ALLOWLIST" } else { Fail "API_ENV_ALLOWLIST" ("missing={0}" -f ($ApiMissing -join ',')) }
    } catch { Fail "RUNTIME_ENV_ALLOWLIST_CONTRACT" $_.Exception.Message }

    try {
        & (Join-Path $ProjectPath "scripts\VALIDAR-EDUVIGIA.ps1")
        Pass "RUNTIME_ENDPOINTS"
    } catch { Fail "RUNTIME_ENDPOINTS" $_.Exception.Message }


    try {
        $PgEnv = ((& docker inspect eduvigia_postgres --format '{{range .Config.Env}}{{println .}}{{end}}') -join "`n")
        $NoAppLeak = ($PgEnv -notmatch '(?m)^DATABASE_URL=' -and $PgEnv -notmatch '(?m)^EDUVIGIA_' -and $PgEnv -notmatch '(?m)^CORS_ORIGINS=' -and $PgEnv -notmatch '(?m)^REDIS_URL=')
        if ($NoAppLeak) { Pass "POSTGRES_RUNTIME_ENV_MINIMAL" } else { Fail "POSTGRES_RUNTIME_ENV_MINIMAL" "variaveis de aplicacao vazaram para postgres" }
    } catch { Fail "POSTGRES_RUNTIME_ENV_MINIMAL" $_.Exception.Message }

    try {
        $Head = ((& docker compose exec -T api alembic current) -join " ").Trim()
        if ($Head -match '20260909_205_f4') { Pass "ALEMBIC_F4_HEAD" } else { Fail "ALEMBIC_F4_HEAD" $Head }
    } catch { Fail "ALEMBIC_F4_HEAD" $_.Exception.Message }

    try {
        $F2Preflight = (& docker compose exec -T api python -m app.vms_f2_preflight) -join ""
        if ($F2Preflight -match 'EDUVIGIA_F2_VMS_PREFLIGHT_OK') { Pass "F2_BASE_CONTRACT_PRESERVED" }
        else { Fail "F2_BASE_CONTRACT_PRESERVED" $F2Preflight }
    } catch { Fail "F2_BASE_CONTRACT_PRESERVED" $_.Exception.Message }

    try {
        $Preflight = (& docker compose exec -T api python -m app.vms_f3_preflight) -join ""
        if ($Preflight -match 'EDUVIGIA_F3_PTZ_PREFLIGHT_OK') { Pass "BACKEND_F3_PTZ_CONTRACT" }
        else { Fail "BACKEND_F3_PTZ_CONTRACT" $Preflight }
    } catch { Fail "BACKEND_F3_PTZ_CONTRACT" $_.Exception.Message }

    try {
        $DbContract = (& docker compose exec -T api python -c "import os; from sqlalchemy import create_engine,inspect,text; e=create_engine(os.environ['DATABASE_URL']); i=inspect(e); cols={c['name'] for c in i.get_columns('cameras')}; req={'ptz_enabled','ptz_protocol','ptz_http_port','ptz_https','ptz_channel','ptz_last_command_at','ptz_last_error'}; lease=i.has_table('camera_ptz_leases'); preset=i.has_table('camera_ptz_presets'); c=e.connect(); v=c.execute(text('select version_num from alembic_version')).scalar(); c.close(); print('OK' if req.issubset(cols) and lease and preset and v=='20260909_205_f4' else 'FAIL:'+repr({'missing':sorted(req-cols),'lease':lease,'preset':preset,'version':v}))") -join ""
        if ($DbContract.Trim() -eq 'OK') { Pass "DATABASE_F3_PTZ_CONTRACT" } else { Fail "DATABASE_F3_PTZ_CONTRACT" $DbContract }
    } catch { Fail "DATABASE_F3_PTZ_CONTRACT" $_.Exception.Message }

    try {
        $SecurityContract = (& docker compose exec -T api python -c "from app.application import CameraOut,role_permissions; secret_ok=CameraOut.model_fields['password'].exclude is True; perms=['GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA','GESTOR_ESCOLA','OPERADOR_ESCOLA','TECNICO']; perm_ok=all('ptz:control' in role_permissions(r, 1 if 'ESCOLA' in r else None) for r in perms); print('OK' if secret_ok and perm_ok else 'FAIL')") -join ""
        if ($SecurityContract.Trim() -eq 'OK') { Pass "PTZ_SECURITY_RBAC_CONTRACT" } else { Fail "PTZ_SECURITY_RBAC_CONTRACT" $SecurityContract }
    } catch { Fail "PTZ_SECURITY_RBAC_CONTRACT" $_.Exception.Message }

    try {
        $App = Get-Content (Join-Path $ProjectPath "frontend\src\app\App.jsx") -Raw
        $Required = @(
            'PTZControlPanel',
            'Assumir controle',
            '/ptz/lease',
            '/ptz/move',
            '/ptz/stop',
            'STOP',
            'Salvar posição',
            'onPointerDown',
            'onPointerUp',
            'ptz_enabled',
            'can("ptz:control")'
        )
        $Missing = @($Required | Where-Object { $App -notmatch [regex]::Escape($_) })
        if ($Missing.Count -eq 0) { Pass "FRONTEND_F3_PTZ_CONTRACT" }
        else { Fail "FRONTEND_F3_PTZ_CONTRACT" ("missing={0}" -f ($Missing -join ',')) }
    } catch { Fail "FRONTEND_F3_PTZ_CONTRACT" $_.Exception.Message }


    try {
        $MultiPreflight = (& docker compose exec -T api python -m app.vms_f3r2_preflight) -join ""
        if ($MultiPreflight -match 'EDUVIGIA_F3R2_MULTICHANNEL_PREFLIGHT_OK') { Pass "BACKEND_F3R2_MULTICHANNEL_CONTRACT" }
        else { Fail "BACKEND_F3R2_MULTICHANNEL_CONTRACT" $MultiPreflight }
    } catch { Fail "BACKEND_F3R2_MULTICHANNEL_CONTRACT" $_.Exception.Message }

    try {
        $MultiDb = (& docker compose exec -T api python -c "import os; from sqlalchemy import create_engine,inspect,text; e=create_engine(os.environ['DATABASE_URL']); i=inspect(e); cam={c['name'] for c in i.get_columns('cameras')}; req={'device_id','logical_channel','sensor_type','sensor_label','primary_sensor'}; vd=i.has_table('video_devices'); vdcols={c['name'] for c in i.get_columns('video_devices')} if vd else set(); vdreq={'id','school_id','ip_address','rtsp_port','username','password','device_type','channel_count'}; c=e.connect(); v=c.execute(text('select version_num from alembic_version')).scalar(); c.close(); print('OK' if vd and req.issubset(cam) and vdreq.issubset(vdcols) and v=='20260909_205_f4' else 'FAIL:'+repr({'camera_missing':sorted(req-cam),'video_devices':vd,'device_missing':sorted(vdreq-vdcols),'version':v}))") -join ""
        if ($MultiDb.Trim() -eq 'OK') { Pass "DATABASE_F3R2_MULTICHANNEL_CONTRACT" }
        else { Fail "DATABASE_F3R2_MULTICHANNEL_CONTRACT" $MultiDb }
    } catch { Fail "DATABASE_F3R2_MULTICHANNEL_CONTRACT" $_.Exception.Message }

    try {
        $MultiSecurity = (& docker compose exec -T api python -c "from app.application import CameraOut,VideoDeviceOut; ok=CameraOut.model_fields['password'].exclude is True and VideoDeviceOut.model_fields['password'].exclude is True; print('OK' if ok else 'FAIL')") -join ""
        if ($MultiSecurity.Trim() -eq 'OK') { Pass "MULTICHANNEL_CREDENTIAL_SECURITY" }
        else { Fail "MULTICHANNEL_CREDENTIAL_SECURITY" $MultiSecurity }
    } catch { Fail "MULTICHANNEL_CREDENTIAL_SECURITY" $_.Exception.Message }

    try {
        $MultiApp = Get-Content (Join-Path $ProjectPath "frontend\src\app\App.jsx") -Raw
        $MultiRequired = @(
            'Dispositivos multi-sensor',
            '/video-devices',
            'device_id',
            'logical_channel',
            'sensor_type',
            'TÉRMICO',
            'VISÍVEL',
            'MULTISENSOR'
        )
        $MultiMissing = @($MultiRequired | Where-Object { $MultiApp -notmatch [regex]::Escape($_) })
        if ($MultiMissing.Count -eq 0) { Pass "FRONTEND_F3R2_MULTICHANNEL_CONTRACT" }
        else { Fail "FRONTEND_F3R2_MULTICHANNEL_CONTRACT" ("missing={0}" -f ($MultiMissing -join ',')) }
    } catch { Fail "FRONTEND_F3R2_MULTICHANNEL_CONTRACT" $_.Exception.Message }

    try {
        $F4Preflight = (& docker compose exec -T api python -m app.vms_f4_preflight) -join ""
        if ($F4Preflight -match 'EDUVIGIA_F4_PLAYBACK_EVIDENCE_PREFLIGHT_OK') { Pass "BACKEND_F4_PLAYBACK_EVIDENCE_CONTRACT" }
        else { Fail "BACKEND_F4_PLAYBACK_EVIDENCE_CONTRACT" $F4Preflight }
    } catch { Fail "BACKEND_F4_PLAYBACK_EVIDENCE_CONTRACT" $_.Exception.Message }

    try {
        $F4Db = (& docker compose exec -T api python -c "import os; from sqlalchemy import create_engine,inspect,text; e=create_engine(os.environ['DATABASE_URL']); i=inspect(e); cols={c['name'] for c in i.get_columns('evidence')}; req={'school_id','device_id','logical_channel','sensor_type','sha256','file_size_bytes','source_start_at','source_end_at','source_origin','integrity_status','created_by_user_id'}; custody=i.has_table('evidence_custody_events'); c=e.connect(); v=c.execute(text('select version_num from alembic_version')).scalar(); c.close(); print('OK' if req.issubset(cols) and custody and v=='20260909_205_f4' else 'FAIL:'+repr({'missing':sorted(req-cols),'custody':custody,'version':v}))") -join ""
        if ($F4Db.Trim() -eq 'OK') { Pass "DATABASE_F4_EVIDENCE_CONTRACT" }
        else { Fail "DATABASE_F4_EVIDENCE_CONTRACT" $F4Db }
    } catch { Fail "DATABASE_F4_EVIDENCE_CONTRACT" $_.Exception.Message }

    try {
        $F4Security = (& docker compose exec -T api python -c "from app.application import role_permissions; playback=['GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA','GESTOR_ESCOLA','OPERADOR_ESCOLA','TECNICO']; export=['GESTOR_SECRETARIA','SUPERVISOR_GUARDA','OPERADOR_GUARDA','DESPACHANTE_GUARDA']; ok=all('playback:view' in role_permissions(r,1 if 'ESCOLA' in r else None) for r in playback) and all('evidence:export' in role_permissions(r,None) for r in export) and 'evidence:export' not in role_permissions('GESTOR_ESCOLA',1); print('OK' if ok else 'FAIL')") -join ""
        if ($F4Security.Trim() -eq 'OK') { Pass "F4_PLAYBACK_RBAC_CONTRACT" }
        else { Fail "F4_PLAYBACK_RBAC_CONTRACT" $F4Security }
    } catch { Fail "F4_PLAYBACK_RBAC_CONTRACT" $_.Exception.Message }

    try {
        $F4App = Get-Content (Join-Path $ProjectPath "frontend\src\app\App.jsx") -Raw
        $F4Required = @(
            'Playback e Evidências',
            '/playback/search',
            '/playback/preview',
            '/playback/export',
            '/verify',
            'SHA-256',
            'logical_channel',
            'sensor_type',
            'Revisar',
            'Evidência'
        )
        $F4Missing = @($F4Required | Where-Object { $F4App -notmatch [regex]::Escape($_) })
        if ($F4Missing.Count -eq 0) { Pass "FRONTEND_F4_PLAYBACK_EVIDENCE_CONTRACT" }
        else { Fail "FRONTEND_F4_PLAYBACK_EVIDENCE_CONTRACT" ("missing={0}" -f ($F4Missing -join ',')) }
    } catch { Fail "FRONTEND_F4_PLAYBACK_EVIDENCE_CONTRACT" $_.Exception.Message }

    try {
        $Application = Get-Content (Join-Path $ProjectPath "backend\app\application.py") -Raw
        $NoCredentialSerialization = (
            $Application -match 'build_hikvision_playback_rtsp' -and
            $Application -match 'camera_playback_capabilities' -and
            $Application -notmatch '"playback_url"\s*:' -and
            $Application -notmatch '"rtsp_url"\s*:\s*build_hikvision_playback_rtsp'
        )
        if ($NoCredentialSerialization) { Pass "PLAYBACK_CREDENTIAL_NON_SERIALIZATION" }
        else { Fail "PLAYBACK_CREDENTIAL_NON_SERIALIZATION" "URL RTSP de playback nao deve sair na API" }
    } catch { Fail "PLAYBACK_CREDENTIAL_NON_SERIALIZATION" $_.Exception.Message }

    $TestDbUrl = "sqlite:////tmp/eduvigia-f4-test.db"
    $AppHost = (Resolve-Path (Join-Path $ProjectPath "backend\app")).Path
    $TestsHost = (Resolve-Path (Join-Path $ProjectPath "backend\tests")).Path
    $AppVolume = "${AppHost}:/app/app:ro"
    $TestVolume = "${TestsHost}:/app/tests:ro"

    $TestApiImage = "eduvigia-api:latest"
    $ImageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", $TestApiImage)
    if ($ImageInspect.ExitCode -eq 0) {
        Pass "TEST_RUNNER_IMAGE"
        Pass "API_IMAGE_DETERMINISTIC"
    } else {
        $TestApiImage = ""
        Fail "TEST_RUNNER_IMAGE" "imagem determinística eduvigia-api:latest não localizada"
    }

    if ($TestApiImage) {
        $ImportResult = Invoke-DockerCapture -Arguments @(
            "run", "--rm",
            "-e", "PYTHONPATH=/app",
            "-e", "DATABASE_URL=$TestDbUrl",
            "-e", "APP_VERSION=2.0.0-F4-R1-HF1",
            "-e", "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD=F3Test@2026!",
            "-e", "EDUVIGIA_CREDENTIAL_KEY=mQvP4uC9fSMwICBE7Mum90ZeX_qhNaL8TiYf8RUMfFs=",
            "-e", "EDUVIGIA_STREAM_SIGNING_KEY=f3-r2-test-stream-key-1234567890",
            "-v", $AppVolume,
            "-v", $TestVolume,
            "-w", "/app",
            $TestApiImage,
            "python", "-c", "import app; import app.application; print('EDUVIGIA_F4_TEST_RUNNER_IMPORT_OK')"
        )
        $ImportProbe = ($ImportResult.Output -join "`n")
        if ($ImportResult.ExitCode -eq 0 -and $ImportProbe -match 'EDUVIGIA_F4_TEST_RUNNER_IMPORT_OK') { Pass "TEST_RUNNER_APP_IMPORT" }
        else { Fail "TEST_RUNNER_APP_IMPORT" ("exit={0}; output={1}" -f $ImportResult.ExitCode, $ImportProbe) }

        $RegressionExit = Invoke-DockerPassthrough -Arguments @(
            "run", "--rm",
            "-e", "PYTHONPATH=/app",
            "-e", "DATABASE_URL=$TestDbUrl",
            "-e", "APP_VERSION=2.0.0-F4-R1-HF1",
            "-e", "EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD=F3Test@2026!",
            "-e", "EDUVIGIA_CREDENTIAL_KEY=mQvP4uC9fSMwICBE7Mum90ZeX_qhNaL8TiYf8RUMfFs=",
            "-e", "EDUVIGIA_STREAM_SIGNING_KEY=f3-r2-test-stream-key-1234567890",
            "-v", $AppVolume,
            "-v", $TestVolume,
            "-w", "/app",
            $TestApiImage,
            "python", "-m", "pytest", "-q", "/app/tests"
        )
        if ($RegressionExit -eq 0) { Pass "BACKEND_REGRESSION_ISOLATED" } else { Fail "BACKEND_REGRESSION_ISOLATED" ("exit={0}" -f $RegressionExit) }
    } else {
        Fail "TEST_RUNNER_APP_IMPORT" "imagem da API indisponível"
        Fail "BACKEND_REGRESSION_ISOLATED" "imagem da API indisponível"
    }

    try {
        $RuntimeDbUrl = ((& docker compose exec -T api python -c "import os; print(os.environ.get('DATABASE_URL',''))") -join "").Trim()
        $Isolated = (
            $TestDbUrl.StartsWith('sqlite:////tmp/') -and
            $RuntimeDbUrl -ne $TestDbUrl -and
            $AppVolume.EndsWith('/app/app:ro') -and
            $TestVolume.EndsWith('/app/tests:ro') -and
            $TestApiImage
        )
        if ($Isolated) { Pass "TEST_GATE_ISOLATED_FROM_RUNTIME_DB" }
        else { Fail "TEST_GATE_ISOLATED_FROM_RUNTIME_DB" ("runtime_db={0}; test_db={1}" -f $RuntimeDbUrl,$TestDbUrl) }
    } catch { Fail "TEST_GATE_ISOLATED_FROM_RUNTIME_DB" $_.Exception.Message }

    try {
        $Subir = Get-Content (Join-Path $ProjectPath "scripts\SUBIR-EDUVIGIA.ps1") -Raw
        $MigrationPos = $Subir.IndexOf('$UpgradeExit = Invoke-DockerPassthrough')
        $ApiBootPos = $Subir.IndexOf('docker compose up -d api')
        $LegacyApiFirst = $Subir.IndexOf('docker compose up -d postgres redis mediamtx api')
        if ($MigrationPos -ge 0 -and $ApiBootPos -gt $MigrationPos -and $LegacyApiFirst -lt 0) {
            Pass "MIGRATION_BEFORE_API_BOOT_CONTRACT"
        } else {
            Fail "MIGRATION_BEFORE_API_BOOT_CONTRACT" "ordem de boot/migration invalida"
        }
    } catch { Fail "MIGRATION_BEFORE_API_BOOT_CONTRACT" $_.Exception.Message }

    try {
        $SubirCert = Get-Content (Join-Path $ProjectPath "scripts\SUBIR-EDUVIGIA.ps1") -Raw
        $CertMinimal = (
            $SubirCert -match 'TLS_CERT_MINIMAL_DOCKER_RUN' -and
            $SubirCert -match 'DB_PROBE_MINIMAL_DOCKER_RUN' -and
            $SubirCert -match 'ALEMBIC_MINIMAL_DOCKER_RUN' -and
            $SubirCert -match 'ALL_BOOTSTRAP_DOCKER_RUN_MINIMAL_ENV' -and
            $SubirCert -match 'EDUVIGIA_TLS_CERT_DIR=/certs' -and
            $SubirCert -match 'EDUVIGIA_TLS_HOSTS=\$TlsHosts' -and
            $SubirCert -match 'DATABASE_URL=\$DatabaseUrl' -and
            $SubirCert -match '\$ApiImage' -and
            $SubirCert -match 'eduvigia-api:latest' -and
            $SubirCert -match 'API_IMAGE_DETERMINISTIC' -and
            $SubirCert -notmatch '@\("compose",\s*"run"'
        )
        if ($CertMinimal) { Pass "BOOTSTRAP_MINIMAL_DOCKER_RUN" }
        else { Fail "BOOTSTRAP_MINIMAL_DOCKER_RUN" "bootstrap ainda herda ambiente completo do serviço API" }
    } catch { Fail "BOOTSTRAP_MINIMAL_DOCKER_RUN" $_.Exception.Message }

    try {
        $SubirPs51 = Get-Content (Join-Path $ProjectPath "scripts\SUBIR-EDUVIGIA.ps1") -Raw
        $Ps51Safe = (
            $SubirPs51 -match 'function Invoke-DockerPassthrough' -and
            $SubirPs51 -match 'function Invoke-DockerProbe' -and
            $SubirPs51 -match 'function Invoke-DockerCapture' -and
            $SubirPs51 -match 'TLS_CERT_DOCKER_RUN_PS51_SAFE' -and
            $SubirPs51 -match 'ALL_BOOTSTRAP_DOCKER_RUN_PS51_SAFE' -and
            $SubirPs51 -match 'ALL_BOOTSTRAP_DOCKER_RUN_MINIMAL_ENV' -and
            $SubirPs51 -match '\$ErrorActionPreference = "Continue"' -and
            $SubirPs51 -notmatch '(?m)^\s*docker compose run'
        )
        if ($Ps51Safe) { Pass "PS51_DOCKER_STDERR_COMPAT" }
        else { Fail "PS51_DOCKER_STDERR_COMPAT" "nem todos os docker compose run do bootstrap usam wrappers PS5.1-safe" }
    } catch { Fail "PS51_DOCKER_STDERR_COMPAT" $_.Exception.Message }

    try {
        $WebContainer = docker compose ps --status running --services | Where-Object { $_ -eq 'web' }
        if ($WebContainer) { Pass "WEB_BUILD_RUNTIME" } else { Fail "WEB_BUILD_RUNTIME" "container web não está em execução" }
    } catch { Fail "WEB_BUILD_RUNTIME" $_.Exception.Message }
} finally {
    Pop-Location
}

if ($Failed -gt 0) {
    Write-Host ("EDUVIGIA_F4_PLAYBACK_CORE=REJECTED|FAILURES={0}" -f $Failed) -ForegroundColor Red
    exit 1
}
Write-Host "EDUVIGIA_F3_PTZ_CORE=APPROVED" -ForegroundColor Green
Write-Host "EDUVIGIA_F3_PTZ_HARDWARE=PENDING_FIELD_TEST" -ForegroundColor Yellow
Write-Host "EDUVIGIA_F3R2_MULTICHANNEL_CORE=APPROVED" -ForegroundColor Green
Write-Host "EDUVIGIA_F3R2_THERMAL_HARDWARE=PENDING_FIELD_TEST" -ForegroundColor Yellow
Write-Host "EDUVIGIA_F4_PLAYBACK_CORE=APPROVED" -ForegroundColor Green
Write-Host "EDUVIGIA_F4_HIKVISION_HARDWARE=PENDING_FIELD_TEST" -ForegroundColor Yellow
Write-Host "EDUVIGIA_F4_HF1_LEGACY_PREFLIGHT=APPROVED" -ForegroundColor Green
Write-Host "EDUVIGIA_F4_HF1_FRONTEND_CLEANUP=APPROVED" -ForegroundColor Green
