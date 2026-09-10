# EduVigIA 2.0.0-F1-R1-HF2 — Media DEV/PROD

## Causa confirmada
No Windows/Chrome, o MediaMTX local em HTTPS usava certificado autoassinado. O teste sem ignorar TLS retornou `SEC_E_UNTRUSTED_ROOT`, enquanto `curl -k` recebeu HTTP 302. O transporte estava ativo, mas o navegador não confiava na CA local.

## Correção
- DEV (`docker-compose.yml`): WebRTC/HLS em HTTP, portas 18889/18888.
- PROD (`docker-compose.prod.yml`): WebRTC/HLS permanecem em HTTPS.
- Novo `mediamtx/mediamtx.prod.yml` preserva TLS em produção.
- O `.env` DEV usa `EDUVIGIA_MEDIA_PUBLIC_SCHEME=http`.
- O Compose PROD força `EDUVIGIA_MEDIA_PUBLIC_SCHEME=https`, independentemente do `.env` DEV.
- Nenhuma alteração em câmeras, RTSP, NVR, banco ou migration.
- Regressão automatizada para contratos HTTP DEV / HTTPS PROD.

## Gate final
`EDUVIGIA_F1_HF2_MEDIA_DEV_PROD=APPROVED`
