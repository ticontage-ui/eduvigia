# EduVigIA Emergency Chat — PTT Recording & History Contract

Version: 0.7.0-R1

## Scope

- Every accepted PTT transmission is recorded server-side.
- The recorder persists the same binary WEBM/Opus bytes accepted by the PTT relay.
- One recording is associated with one PTT floor.
- Maximum live PTT transmission remains 30 seconds.
- Recording storage limit is 8 MB per transmission.
- SHA-256 is calculated server-side over the stored transmission.
- History is isolated by emergency channel.
- Schools cannot access recordings from another school.
- Municipal Guard and Education Secretariat retain only the channels for which their identity is a member.
- Playback requires an authorized identity on every request.
- Recordings with zero bytes or an exceeded storage cap are marked ABORTED and are not shown in history.
- Release, timeout and disconnect all finalize the recording.
- A recording failure must never leave the radio floor locked.
- Existing PTT transport remains WebSocket + WEBM/Opus.

## Retention

V0.7-R1 does not automatically delete READY recordings. Retention policy will be defined separately before production rollout. This avoids silently destroying operational evidence before the municipality defines the applicable retention rule.

## Integrity boundary

SHA-256 provides file-integrity verification for the bytes stored by the server. V0.7-R1 does not claim qualified digital signature, timestamp authority or legal chain-of-custody certification.