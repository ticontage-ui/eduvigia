# EduVigIA 2.0.0-F1-R1-HF2 — Media TLS Hotfix

Corrige regressão em vídeo introduzida na F0/F1: o backend herdava `http` da requisição do painel e gerava URLs HTTP para portas HLS/WebRTC configuradas com TLS.

## Correção
- `EDUVIGIA_MEDIA_PUBLIC_SCHEME=https` por padrão.
- URLs WebRTC/HLS passam a usar HTTPS mesmo com painel direto em HTTP.
- Bases públicas explícitas continuam tendo prioridade.
- Preflight de vídeo atualizado para MediaMTX TLS de laboratório.
- Teste de regressão adicionado.

Nenhuma alteração em NVR, câmera, RTSP ou banco de dados.
