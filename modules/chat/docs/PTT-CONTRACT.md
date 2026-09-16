# EduVigIA Emergency Chat — Institutional PTT Contract

Version: 0.6.0-R1

- PTT is half-duplex and institutional.
- One speaker per emergency channel.
- School-to-school PTT is denied.
- Redis SET NX provides atomic floor acquisition.
- Maximum transmission: 30 seconds.
- Floor TTL: 35 seconds.
- Release on pointer release, browser focus loss, disconnect or timeout.
- Binary audio from identities that do not own the floor is discarded server-side.
- Media transport in R1: authenticated WebSocket with WEBM/Opus chunks.
- No PTT recording is stored in V0.6.
- No database migration is required.

This R1 transport is suitable for the current isolated/intranet phase. A later high-scale transport can move to WebRTC SFU/TURN without changing the authorization and floor-control contract.