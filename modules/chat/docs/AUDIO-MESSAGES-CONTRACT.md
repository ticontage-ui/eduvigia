# EduVigIA Emergency Chat — Audio Messages Contract

Version: 0.5.0-R1

- Asynchronous audio messages inside the institutional Emergency Channel.
- School isolation is unchanged.
- Browser recording uses MediaRecorder/getUserMedia.
- Preferred format: WEBM + Opus; fallback OGG + Opus or M4A/MP4 audio.
- UI recording limit: 60 seconds with automatic stop.
- Server audio size limit: 12 MB.
- Audio uses the same persistent attachment storage, SHA-256 and channel authorization.
- Extension, MIME and container signature are validated.
- This phase is not PTT and not a voice call.
- PTT remains planned for V0.6.
- Server-side media-duration inspection is not claimed in V0.5; production hardening may add ffprobe/equivalent.