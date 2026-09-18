# EduVigIA Chat — V0.8-R2.2 TLS/LAN + LIVE Audio

## Purpose

Enable real LIVE microphone publication from GESTOR_ESCOLA and automatic
subscription for authorized Guarda/Secretaria operators.

## Security model

- Microphone activation always starts from an explicit manager action.
- There is no automatic or hidden microphone activation.
- Once LIVE is active, authorized operators do not need manager approval to hear.
- OPERADOR_ESCOLA remains blocked.
- Cross-school access remains server-side blocked.
- No recording/Egress service is enabled.

## LAN transport

Chat HTTPS:
- `https://<LAN_IP>:16443`

LiveKit signaling:
- `wss://<LAN_IP>:16444`

WebRTC media:
- TCP `17881`
- UDP `17882`

A locally generated CA signs the LAN server certificate. Client machines used
for QA must explicitly trust `modules/chat/infra/crisis-certs.local/rootCA.crt`.

The CA private key remains local and ignored by Git.

## Browser policy

If browser autoplay prevents operator audio, the UI shows
`Ativar som no navegador`. This is a browser playback permission and is not an
approval request to the school manager.

## Production note

This LAN certificate/TLS design is for controlled QA. Production deployment
must use the official deployment hostname/certificate, firewall policy and TURN
strategy.
