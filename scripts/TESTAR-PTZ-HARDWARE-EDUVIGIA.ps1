[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][int]$CameraId,
    [switch]$ExecuteMovement,
    [string]$ProjectPath = "$env:USERPROFILE\Documents\eduvigia"
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectPath
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " EduVigIA F3 - PTZ Hardware Check" -ForegroundColor Cyan
Write-Host " CameraId=$CameraId" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not $ExecuteMovement) {
    Write-Host "CHECK_ONLY=YES" -ForegroundColor Yellow
    Write-Host "Este script não movimentará a câmera sem -ExecuteMovement." -ForegroundColor Yellow
    Write-Host "Use o painel em http://localhost:5177 para o teste funcional autenticado." -ForegroundColor Green
    exit 0
}

Write-Host "MOVEMENT_TEST_REQUIRES_AUTHENTICATED_UI=YES" -ForegroundColor Yellow
Write-Host "Por segurança, o movimento físico deve ser feito no Monitoramento, assumindo o lease PTZ e mantendo visão da câmera." -ForegroundColor Yellow
Write-Host "Abra: http://localhost:5177" -ForegroundColor Green
