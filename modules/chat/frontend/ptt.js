const pttPanelEl = document.getElementById("pttPanel");
const pttStatusEl = document.getElementById("pttStatus");
const pttSpeakerEl = document.getElementById("pttSpeaker");
const pttButtonEl = document.getElementById("pttButton");
const pttTimerEl = document.getElementById("pttTimer");
const pttEnableAudioEl = document.getElementById("pttEnableAudio");
const pttRemoteAudioEl = document.getElementById("pttRemoteAudio");

const PTT_MAX_SECONDS = 30;
const PTT_CHUNK_MS = 250;

let pttSocket = null;
let pttSocketChannel = null;
let pttReconnectTimer = null;
let pttHeartbeat = null;
let pttWantToTalk = false;
let pttOwnFloorId = null;
let pttRemoteSpeaker = null;
let pttStream = null;
let pttRecorder = null;
let pttStartedAt = 0;
let pttTimerHandle = null;
let pttMediaSource = null;
let pttSourceBuffer = null;
let pttPendingChunks = [];
let pttLastKnownChannel = null;
let pttLastKnownIdentity = null;
let pttCurrentChannelId = null;
let pttCurrentIdentity = null;

function pttReadChatContext() {
  const provider = window.EduVigIAChatContext;

  if (!provider || typeof provider.get !== "function") {
    return {
      identityId: null,
      channelId: null
    };
  }

  const context = provider.get() || {};

  return {
    identityId: context.identityId || null,
    channelId: context.channelId || null
  };
}

function pttSetState(mode, status, speaker = "") {
  pttPanelEl.dataset.state = mode;
  pttStatusEl.textContent = status;
  pttSpeakerEl.textContent = speaker;
  pttButtonEl.disabled = mode !== "ready" && mode !== "transmitting";
}

function pttFormatTime(seconds) {
  const safe = Math.max(0, Math.min(PTT_MAX_SECONDS, seconds));
  return `00:${String(safe).padStart(2, "0")} / 00:30`;
}

function pttUpdateTimer() {
  if (!pttStartedAt) {
    pttTimerEl.textContent = "00:00 / 00:30";
    return;
  }
  pttTimerEl.textContent = pttFormatTime(Math.floor((Date.now() - pttStartedAt) / 1000));
}

function pttPreferredMime() {
  for (const mime of ["audio/webm;codecs=opus", "audio/webm"]) {
    if (MediaRecorder.isTypeSupported?.(mime)) return mime;
  }
  return "";
}

function pttStopTracks() {
  if (pttStream) for (const track of pttStream.getTracks()) track.stop();
  pttStream = null;
}

function pttResetLocal() {
  if (pttTimerHandle) clearInterval(pttTimerHandle);
  pttTimerHandle = null;
  pttStartedAt = 0;
  pttUpdateTimer();
  pttRecorder = null;
  pttStopTracks();
}

function pttCloseRemote() {
  pttPendingChunks = [];
  pttSourceBuffer = null;
  pttMediaSource = null;
  pttRemoteAudioEl.pause();
  pttRemoteAudioEl.removeAttribute("src");
  pttRemoteAudioEl.load();
}

function pttPump() {
  if (!pttSourceBuffer || pttSourceBuffer.updating || !pttPendingChunks.length) return;
  try { pttSourceBuffer.appendBuffer(pttPendingChunks.shift()); }
  catch (error) { console.error("Falha no player PTT:", error); }
}

function pttBeginRemote() {
  pttCloseRemote();
  const mime = "audio/webm;codecs=opus";
  if (!window.MediaSource || !MediaSource.isTypeSupported(mime)) return;
  pttMediaSource = new MediaSource();
  pttRemoteAudioEl.src = URL.createObjectURL(pttMediaSource);
  pttMediaSource.addEventListener("sourceopen", () => {
    try {
      pttSourceBuffer = pttMediaSource.addSourceBuffer(mime);
      pttSourceBuffer.mode = "sequence";
      pttSourceBuffer.addEventListener("updateend", pttPump);
      pttPump();
      const playPromise = pttRemoteAudioEl.play();
      playPromise?.catch?.(() => { pttEnableAudioEl.hidden = false; });
    } catch (error) { console.error(error); }
  }, {once: true});
}

async function pttStartPublishing() {
  try {
    pttStream = await navigator.mediaDevices.getUserMedia({
      audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
      video: false
    });
    const mime = pttPreferredMime();
    if (!mime) throw new Error("WEBM/Opus indisponível");
    pttRecorder = new MediaRecorder(pttStream, {mimeType: mime});
    pttRecorder.addEventListener("dataavailable", async event => {
      if (!event.data?.size || !pttOwnFloorId || pttSocket?.readyState !== WebSocket.OPEN) return;
      pttSocket.send(await event.data.arrayBuffer());
    });
    pttRecorder.addEventListener("stop", pttResetLocal);
    pttRecorder.start(PTT_CHUNK_MS);
    pttStartedAt = Date.now();
    pttTimerHandle = setInterval(pttUpdateTimer, 250);
    pttSetState("transmitting", "TRANSMITINDO", "Sua voz está sendo enviada ao canal.");
  } catch (error) {
    pttResetLocal();
    alert(error?.name === "NotAllowedError" ? "Permita o acesso ao microfone para usar o PTT." : "Não foi possível iniciar a transmissão PTT.");
    await pttReleaseFloor();
  }
}

function pttStopPublishing() {
  if (pttRecorder?.state === "recording") pttRecorder.stop();
  else pttResetLocal();
}

async function pttRequestFloor() {
  if (!pttCurrentChannelId || !pttCurrentIdentity || pttOwnFloorId || !pttWantToTalk) return;
  try {
    const result = await jsonFetch(`/api/ptt/channels/${encodeURIComponent(pttCurrentChannelId)}/floor/request`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({identity_id: pttCurrentIdentity})
    });
    if (!pttWantToTalk) {
      if (result.granted) { pttOwnFloorId = result.floor_id; await pttReleaseFloor(); }
      return;
    }
    if (!result.granted) {
      pttSetState("busy", "CANAL OCUPADO", `${result.floor?.identity_id || "Outro operador"} está falando.`);
      return;
    }
    pttOwnFloorId = result.floor_id;
    await pttStartPublishing();
  } catch (error) {
    pttSetState("ready", "PTT disponível", "Canal livre");
    alert(error.message || "Não foi possível solicitar o PTT.");
  }
}

async function pttReleaseFloor() {
  const floorId = pttOwnFloorId;
  pttOwnFloorId = null;
  pttStopPublishing();
  if (!floorId || !pttCurrentChannelId || !pttCurrentIdentity) return;
  try {
    await jsonFetch(`/api/ptt/channels/${encodeURIComponent(pttCurrentChannelId)}/floor/release`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({identity_id: pttCurrentIdentity, floor_id: floorId})
    });
  } catch (error) { console.error("Falha ao liberar PTT:", error); }
}

function pttDisconnectSocket() {
  if (pttReconnectTimer) clearTimeout(pttReconnectTimer);
  if (pttHeartbeat) clearInterval(pttHeartbeat);
  pttReconnectTimer = null;
  pttHeartbeat = null;
  if (pttSocket) {
    pttSocket.onclose = null;
    pttSocket.close();
    pttSocket = null;
  }
  pttSocketChannel = null;
}

function pttConnectSocket() {
  pttDisconnectSocket();
  if (!pttCurrentChannelId || !pttCurrentIdentity) {
    pttSetState("disabled", "PTT indisponível", "Selecione um canal");
    return;
  }
  const channel = pttCurrentChannelId;
  const identity = pttCurrentIdentity;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  pttSocket = new WebSocket(`${protocol}//${location.host}/ws/ptt?identity_id=${encodeURIComponent(identity)}&channel_id=${encodeURIComponent(channel)}`);
  pttSocket.binaryType = "arraybuffer";
  pttSocketChannel = channel;
  pttSetState("connecting", "Conectando PTT…", "");
  pttSocket.onopen = () => {
    pttHeartbeat = setInterval(() => {
      if (pttSocket?.readyState === WebSocket.OPEN) pttSocket.send("ping");
    }, 20000);
  };
  pttSocket.onmessage = event => {
    if (typeof event.data !== "string") {
      if (pttRemoteSpeaker) { pttPendingChunks.push(event.data); pttPump(); }
      return;
    }
    if (event.data === "pong") return;
    let payload;
    try { payload = JSON.parse(event.data); } catch { return; }
    if (payload.type === "ptt.ready") {
      if (payload.floor?.identity_id && payload.floor.identity_id !== pttCurrentIdentity) {
        pttRemoteSpeaker = payload.floor.identity_id;
        pttBeginRemote();
        pttSetState("busy", "CANAL OCUPADO", `${payload.floor.identity_id} está falando.`);
      } else {
        pttRemoteSpeaker = null;
        pttSetState("ready", "PTT disponível", "Canal livre");
      }
      return;
    }
    if (payload.type === "ptt.speaker.started") {
      if (payload.identity_id === pttCurrentIdentity) return;
      pttRemoteSpeaker = payload.identity_id;
      pttBeginRemote();
      pttSetState("busy", "CANAL OCUPADO", `${payload.display_name || payload.identity_id} está falando.`);
      return;
    }
    if (payload.type === "ptt.speaker.ended") {
      if (payload.identity_id === pttCurrentIdentity && pttOwnFloorId) {
        pttOwnFloorId = null;
        pttStopPublishing();
      }
      pttRemoteSpeaker = null;
      pttCloseRemote();
      if (pttCurrentChannelId) pttSetState("ready", "PTT disponível", "Canal livre");
    }
  };
  pttSocket.onclose = () => {
    pttSetState("connecting", "Reconectando PTT…", "");
    pttReconnectTimer = setTimeout(() => {
      if (pttCurrentChannelId === channel && pttCurrentIdentity === identity) pttConnectSocket();
    }, 1500);
  };
  pttSocket.onerror = () => pttSocket?.close();
}

function pttApplyChatContext(context = {}) {
  const nextIdentity = context.identityId || null;
  const nextChannel = context.channelId || null;

  if (
    nextChannel === pttCurrentChannelId &&
    nextIdentity === pttCurrentIdentity
  ) {
    return;
  }

  const previousChannel = pttCurrentChannelId;
  const previousIdentity = pttCurrentIdentity;

  if (pttWantToTalk || pttOwnFloorId) {
    pttWantToTalk = false;
    pttReleaseFloor();
  }

  pttCurrentChannelId = nextChannel;
  pttCurrentIdentity = nextIdentity;

  pttLastKnownChannel = nextChannel;
  pttLastKnownIdentity = nextIdentity;

  console.info("PTT context changed", {
    previousIdentity,
    previousChannel,
    identityId: pttCurrentIdentity,
    channelId: pttCurrentChannelId
  });

  if (!pttCurrentIdentity) {
    pttDisconnectSocket();
    pttSetState(
      "disabled",
      "PTT indisponível",
      "Selecione um perfil"
    );
    return;
  }

  if (!pttCurrentChannelId) {
    pttDisconnectSocket();
    pttSetState(
      "disabled",
      "PTT indisponível",
      "Selecione um canal"
    );
    return;
  }

  pttSetState(
    "connecting",
    "Conectando PTT…",
    "Validando canal selecionado"
  );

  pttConnectSocket();
}

function pttSynchronizeContext() {
  const context = pttReadChatContext();
  pttApplyChatContext(context);
}

function pttPressStart(event) {
  if (pttButtonEl.disabled) return;
  event.preventDefault();
  pttWantToTalk = true;
  pttButtonEl.setPointerCapture?.(event.pointerId);
  pttRequestFloor();
}

function pttPressEnd(event) {
  event?.preventDefault?.();
  pttWantToTalk = false;
  if (pttOwnFloorId) pttReleaseFloor();
}

pttButtonEl.addEventListener("pointerdown", pttPressStart);
pttButtonEl.addEventListener("pointerup", pttPressEnd);
pttButtonEl.addEventListener("pointercancel", pttPressEnd);
pttButtonEl.addEventListener("lostpointercapture", pttPressEnd);
pttButtonEl.addEventListener("contextmenu", event => event.preventDefault());
pttEnableAudioEl.addEventListener("click", async () => {
  try { await pttRemoteAudioEl.play(); pttEnableAudioEl.hidden = true; } catch {}
});
window.addEventListener("blur", () => {
  if (pttWantToTalk || pttOwnFloorId) {
    pttWantToTalk = false;
    pttReleaseFloor();
  }
});
window.addEventListener("beforeunload", () => {
  pttWantToTalk = false;
  pttStopPublishing();
  pttDisconnectSocket();
});

window.addEventListener("eduvigia:chat-context", event => {
  pttApplyChatContext(event.detail || {});
});

/*
 * Initial snapshot covers the case where app.js completed its bootstrap
 * before ptt.js finished loading.
 */
pttApplyChatContext(pttReadChatContext());

/*
 * Low-frequency fallback only. Normal operation is event-driven.
 */
setInterval(() => {
  const context = pttReadChatContext();

  if (
    context.identityId !== pttCurrentIdentity ||
    context.channelId !== pttCurrentChannelId
  ) {
    pttApplyChatContext(context);
  }
}, 2000);
