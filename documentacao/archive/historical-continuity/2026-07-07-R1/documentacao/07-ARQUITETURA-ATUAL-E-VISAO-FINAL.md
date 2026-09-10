# Arquitetura Atual e Visão Final

## Atual

```text
Câmera/NVR -> RTSP -> MediaMTX -> WebRTC/HLS -> Navegador
                         |
                         +-> API EduVigIA
API -> PostgreSQL / Redis / Alertas / Ocorrências / Evidências
```

O NVR é o gravador principal. O MediaMTX é gateway e distribuidor.

## Futuro com IA

```text
Câmeras -> NVR -> MediaMTX -> Navegador
                    |
                    +-> Servidor de IA
                           |
                           +-> Evento e snapshot
                           v
                       API EduVigIA
                           |
                           v
                    Validação humana
```

Se a IA parar, gravação, login e monitoramento devem continuar.

Bem-Estar será módulo separado, com dados sensíveis, acesso restrito e auditoria própria.
