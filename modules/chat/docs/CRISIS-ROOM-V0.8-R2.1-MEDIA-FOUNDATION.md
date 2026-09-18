# EduVigIA Chat — V0.8-R2.1 Media Foundation

## Scope

This phase adds an isolated, self-hosted LiveKit media foundation to the Chat
module. It does not yet activate microphone capture in the Crisis Room UI.

## Roles

- GESTOR_ESCOLA: publish microphone only; no subscription in R2.1.
- GUARDA/SECRETARIA: subscribe only; cannot publish.
- OPERADOR_ESCOLA: no media token.
- A manager from another school cannot receive a token for the room.

## Security

Tokens are minted only by the Chat backend after server-side RBAC and school
scope validation.

LiveKit room and participant identities are opaque SHA-256-derived identifiers.
School codes, user display names, email addresses and phone numbers are not used
as LiveKit room/participant identities.

The API key and secret are stored only in ignored local configuration files:

- infra/.env.crisis-media.local
- infra/crisis-livekit.local.yaml

They must never be committed.

## Local development transport

R2.1 binds LiveKit signaling and RTC ports to localhost:

- TCP 17880 — signaling/API
- TCP 17881 — ICE/TCP
- UDP 17882 — ICE/UDP mux

This is intentionally a local foundation. Cross-device browser microphone tests
are deferred until the TLS/LAN transport gate in R2.2.

## Recording

No recording or Egress service is configured.

## Next

V0.8-R2.2 will add secure browser/mobile transport, LIVE audio publication by
GESTOR_ESCOLA and automatic operator subscription.
