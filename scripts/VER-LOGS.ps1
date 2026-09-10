$Project=Join-Path $env:USERPROFILE 'Documents\eduvigia'
Set-Location $Project
docker compose logs -f --tail=200
