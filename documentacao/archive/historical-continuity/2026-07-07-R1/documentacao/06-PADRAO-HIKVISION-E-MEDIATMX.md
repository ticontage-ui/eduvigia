# Padrão Hikvision e MediaMTX

## Autenticação

O EduVigIA autentica por ISAPI/HTTP Digest, RTSP e ONVIF quando necessário. A senha fica criptografada e não vai para o frontend.

## Rede

- IP fixo
- HTTP 80
- RTSP 554
- SDK 8000
- NTP e GMT-03:00
- sem exposição direta à internet
- acesso remoto por VPN

## MAIN

- H.264
- perfil Main
- 1920×1080
- 15 FPS
- 2048–4096 Kbps
- I-frame 30
- H.264+, Smart Codec e SVC desativados

## SUB

- H.264
- Main ou Baseline
- 704×480 ou 640×360
- 10 FPS
- 512–1024 Kbps
- I-frame 20
- H.264+, Smart Codec e SVC desativados

## URLs

- MAIN: `/Streaming/Channels/101`
- SUB: `/Streaming/Channels/102`

## Teste

1. ping;
2. portas 80, 554 e 8000;
3. VLC MAIN;
4. VLC SUB;
5. primeiro quadro;
6. provisionamento;
7. `ready=true`;
8. `available=true`;
9. WebRTC;
10. mosaico.
