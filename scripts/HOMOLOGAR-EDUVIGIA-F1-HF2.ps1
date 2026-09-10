[CmdletBinding()]
param([string]$ProjectPath = "$env:USERPROFILE\Documents\eduvigia")

$ErrorActionPreference = "Stop"
$Failed = 0
function Pass([string]$Name) { Write-Host ("PASS|{0}" -f $Name) -ForegroundColor Green }
function Fail([string]$Name, [string]$Detail) { $script:Failed++; Write-Host ("FAIL|{0}|{1}" -f $Name, $Detail) -ForegroundColor Red }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " EduVigIA 2.0.0-F1-R1-HF2 - Homologacao Media DEV/PROD" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $ProjectPath "docker-compose.yml"))) { throw "Projeto não localizado: $ProjectPath" }
Push-Location $ProjectPath
try {
    $Version = (Get-Content (Join-Path $ProjectPath "VERSION.txt") -Raw).Trim()
    if ($Version -eq "2.0.0-F1-R1-HF2") { Pass "VERSION" } else { Fail "VERSION" $Version }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectPath "scripts\HOMOLOGAR-EDUVIGIA-F1.ps1") -ProjectPath $ProjectPath
    if ($LASTEXITCODE -eq 0) { Pass "F1_BASE_CONTRACT" } else { Fail "F1_BASE_CONTRACT" "Homologador F1 reprovou" }

    try {
        $DevCompose = (& docker compose config) -join "`n"
        if ($DevCompose -match 'EDUVIGIA_MEDIA_PUBLIC_SCHEME:\s*http') { Pass "DEV_MEDIA_SCHEME_HTTP" }
        else { Fail "DEV_MEDIA_SCHEME_HTTP" "Compose DEV não injeta http" }
    } catch { Fail "DEV_MEDIA_SCHEME_HTTP" $_.Exception.Message }

    try {
        $ProdCompose = (& docker compose -f docker-compose.prod.yml config) -join "`n"
        if ($ProdCompose -match 'EDUVIGIA_MEDIA_PUBLIC_SCHEME:\s*https') { Pass "PROD_MEDIA_SCHEME_HTTPS" }
        else { Fail "PROD_MEDIA_SCHEME_HTTPS" "Compose PROD não injeta https" }
    } catch { Fail "PROD_MEDIA_SCHEME_HTTPS" $_.Exception.Message }

    try {
        $DevMtx = Get-Content (Join-Path $ProjectPath "mediamtx\mediamtx.yml") -Raw
        if ($DevMtx -match '(?m)^hlsEncryption:\s*no\s*$' -and $DevMtx -match '(?m)^webrtcEncryption:\s*no\s*$') { Pass "DEV_MEDIAMTX_PLAIN_HTTP" }
        else { Fail "DEV_MEDIAMTX_PLAIN_HTTP" "DEV ainda exige TLS em HLS/WebRTC" }
    } catch { Fail "DEV_MEDIAMTX_PLAIN_HTTP" $_.Exception.Message }

    try {
        $ProdMtx = Get-Content (Join-Path $ProjectPath "mediamtx\mediamtx.prod.yml") -Raw
        if ($ProdMtx -match '(?m)^hlsEncryption:\s*yes\s*$' -and $ProdMtx -match '(?m)^webrtcEncryption:\s*yes\s*$' -and $ProdMtx -match 'hlsServerCert:' -and $ProdMtx -match 'webrtcServerCert:') { Pass "PROD_MEDIAMTX_TLS" }
        else { Fail "PROD_MEDIAMTX_TLS" "PROD não preserva TLS em HLS/WebRTC" }
    } catch { Fail "PROD_MEDIAMTX_TLS" $_.Exception.Message }

    try {
        $UrlContract = & docker compose exec -T api python -c "from starlette.requests import Request; from app.application import _public_media_base; r=Request({'type':'http','method':'GET','scheme':'http','server':('127.0.0.1',8000),'path':'/','raw_path':b'/','query_string':b'','headers':[(b'host',b'127.0.0.1:8002')],'client':('127.0.0.1',1)}); w=_public_media_base(r,protocol='webrtc'); h=_public_media_base(r,protocol='hls'); print('OK' if w=='http://127.0.0.1:18889' and h=='http://127.0.0.1:18888' else 'FAIL:'+w+'|'+h)"
        $Text = ($UrlContract -join '').Trim()
        if ($Text -eq 'OK') { Pass "DEV_MEDIA_URL_HTTP_CONTRACT" } else { Fail "DEV_MEDIA_URL_HTTP_CONTRACT" $Text }
    } catch { Fail "DEV_MEDIA_URL_HTTP_CONTRACT" $_.Exception.Message }

    foreach ($Item in @(
        @{Name='WEBRTC_HTTP_ENDPOINT'; Url='http://127.0.0.1:18889/teste'},
        @{Name='HLS_HTTP_ENDPOINT'; Url='http://127.0.0.1:18888/teste/index.m3u8'}
    )) {
        try {
            $Code = (& curl.exe -sS -o NUL -w "%{http_code}" --max-time 10 $Item.Url).Trim()
            if ($Code -match '^[234][0-9][0-9]$') { Pass $Item.Name }
            else { Fail $Item.Name ("HTTP={0}" -f $Code) }
        } catch { Fail $Item.Name $_.Exception.Message }
    }

    try {
        $HttpsCode = (& curl.exe -k -sS -o NUL -w "%{http_code}" --max-time 5 https://127.0.0.1:18889/teste).Trim()
        if ($HttpsCode -eq '000') { Pass "DEV_WEBRTC_HTTPS_DISABLED" }
        else { Fail "DEV_WEBRTC_HTTPS_DISABLED" ("HTTPS respondeu HTTP={0}" -f $HttpsCode) }
    } catch { Pass "DEV_WEBRTC_HTTPS_DISABLED" }
} finally {
    Pop-Location
}

if ($Failed -gt 0) {
    Write-Host ("EDUVIGIA_F1_HF2_MEDIA_DEV_PROD=REJECTED|FAILURES={0}" -f $Failed) -ForegroundColor Red
    exit 1
}
Write-Host "EDUVIGIA_F1_HF2_MEDIA_DEV_PROD=APPROVED" -ForegroundColor Green
