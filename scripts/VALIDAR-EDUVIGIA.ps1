$ErrorActionPreference = "Continue"
$Checks = @(
    @{ Name = "Painel direto"; Url = "http://127.0.0.1:5177" },
    @{ Name = "API health"; Url = "http://127.0.0.1:8002/health" },
    @{ Name = "Liveness"; Url = "http://127.0.0.1:8002/live" },
    @{ Name = "Readiness"; Url = "http://127.0.0.1:8002/ready" },
    @{ Name = "Métricas"; Url = "http://127.0.0.1:8002/metrics" },
    @{ Name = "Proxy HTTP"; Url = "http://127.0.0.1:8088/healthz" },
    @{ Name = "Prometheus"; Url = "http://127.0.0.1:19090/-/ready" }
)
$Failed = 0
foreach ($Check in $Checks) {
    $Ok = $false
    $LastError = ""
    for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
        try {
            $Response = Invoke-WebRequest -Uri $Check.Url -UseBasicParsing -TimeoutSec 10
            if ($Response.StatusCode -ne 200) { throw ("HTTP {0}" -f $Response.StatusCode) }
            Write-Host ("[OK] {0} - HTTP {1}" -f $Check.Name, $Response.StatusCode) -ForegroundColor Green
            $Ok = $true
            break
        } catch {
            $LastError = $_.Exception.Message
            if ($Attempt -lt 3) { Start-Sleep -Seconds 2 }
        }
    }
    if (-not $Ok) {
        $Failed++
        Write-Host ("[FALHA] {0} - {1}" -f $Check.Name, $LastError) -ForegroundColor Red
    }
}
$Tls = Test-NetConnection 127.0.0.1 -Port 18443 -WarningAction SilentlyContinue
if ($Tls.TcpTestSucceeded) {
    Write-Host "[OK] Proxy HTTPS - TCP 18443" -ForegroundColor Green
} else {
    $Failed++
    Write-Host "[FALHA] Proxy HTTPS - TCP 18443" -ForegroundColor Red
}
if ($Failed -gt 0) { throw ("Validação reprovada em {0} item(ns)." -f $Failed) }
Write-Host "VALIDACAO_EDUVIGIA_2.0.0_F2_R1_OK" -ForegroundColor Green
