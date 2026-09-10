[CmdletBinding()]
param([string]$ProjectPath = "$env:USERPROFILE\Documents\eduvigia")

$ErrorActionPreference = "Stop"
$Failed = 0
function Pass([string]$Name) { Write-Host ("PASS|{0}" -f $Name) -ForegroundColor Green }
function Fail([string]$Name, [string]$Detail) { $script:Failed++; Write-Host ("FAIL|{0}|{1}" -f $Name, $Detail) -ForegroundColor Red }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " EduVigIA 2.0.0-F1-R1-HF2 - Homologacao Media TLS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $ProjectPath "docker-compose.yml"))) { throw "Projeto não localizado: $ProjectPath" }
Push-Location $ProjectPath
try {
    $Version = (Get-Content (Join-Path $ProjectPath "VERSION.txt") -Raw).Trim()
    if ($Version -eq "2.0.0-F1-R1-HF2") { Pass "VERSION" } else { Fail "VERSION" $Version }

    # Revalida todos os contratos da F1.
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectPath "scripts\HOMOLOGAR-EDUVIGIA-F1.ps1") -ProjectPath $ProjectPath
    if ($LASTEXITCODE -eq 0) { Pass "F1_BASE_CONTRACT" } else { Fail "F1_BASE_CONTRACT" "Homologador F1 reprovou" }

    try {
        $Compose = (& docker compose config) -join "`n"
        if ($Compose -match 'EDUVIGIA_MEDIA_PUBLIC_SCHEME:\s*https') { Pass "MEDIA_PUBLIC_SCHEME_HTTPS" }
        else { Fail "MEDIA_PUBLIC_SCHEME_HTTPS" "Compose não injeta https" }
    } catch { Fail "MEDIA_PUBLIC_SCHEME_HTTPS" $_.Exception.Message }

    try {
        $Mtx = Get-Content (Join-Path $ProjectPath "mediamtx\mediamtx.yml") -Raw
        if ($Mtx -match '(?m)^hlsEncryption:\s*yes\s*$' -and $Mtx -match '(?m)^webrtcEncryption:\s*yes\s*$') {
            Pass "MEDIAMTX_TLS_ENABLED"
        } else { Fail "MEDIAMTX_TLS_ENABLED" "HLS/WebRTC TLS não está habilitado" }
    } catch { Fail "MEDIAMTX_TLS_ENABLED" $_.Exception.Message }

    try {
        $UrlContract = & docker compose exec -T api python -c "from starlette.requests import Request; from app.application import _public_media_base; r=Request({'type':'http','method':'GET','scheme':'http','server':('127.0.0.1',8000),'path':'/','raw_path':b'/','query_string':b'','headers':[(b'host',b'127.0.0.1:8002')],'client':('127.0.0.1',1)}); w=_public_media_base(r,protocol='webrtc'); h=_public_media_base(r,protocol='hls'); print('OK' if w=='https://127.0.0.1:18889' and h=='https://127.0.0.1:18888' else 'FAIL:'+w+'|'+h)"
        $UrlContractText = ($UrlContract -join '').Trim()
        if ($UrlContractText -eq 'OK') { Pass "MEDIA_URL_HTTPS_CONTRACT" } else { Fail "MEDIA_URL_HTTPS_CONTRACT" $UrlContractText }
    } catch { Fail "MEDIA_URL_HTTPS_CONTRACT" $_.Exception.Message }

    foreach ($Item in @(
        @{Name='WEBRTC_TLS_HANDSHAKE'; Url='https://127.0.0.1:18889/teste'},
        @{Name='HLS_TLS_HANDSHAKE'; Url='https://127.0.0.1:18888/teste/index.m3u8'}
    )) {
        try {
            $Code = (& curl.exe -k -sS -o NUL -w "%{http_code}" --max-time 10 $Item.Url).Trim()
            # 2xx/3xx/4xx provam que o endpoint respondeu HTTPS; 000 representa falha de transporte/TLS.
            if ($Code -match '^[234][0-9][0-9]$') { Pass $Item.Name }
            else { Fail $Item.Name ("HTTP={0}" -f $Code) }
        } catch { Fail $Item.Name $_.Exception.Message }
    }
} finally {
    Pop-Location
}

if ($Failed -gt 0) {
    Write-Host ("EDUVIGIA_F1_HF1_MEDIA_TLS=REJECTED|FAILURES={0}" -f $Failed) -ForegroundColor Red
    exit 1
}
Write-Host "EDUVIGIA_F1_HF1_MEDIA_TLS=APPROVED" -ForegroundColor Green
