const identityEl = document.getElementById("identity");
const identityInfoEl = document.getElementById("identityInfo");
const operatorToolsEl = document.getElementById("operatorTools");
const searchEl = document.getElementById("channelSearch");
const sectionTitleEl = document.getElementById("channelSectionTitle");
const channelsEl = document.getElementById("channels");
const channelCountEl = document.getElementById("channelCount");
const messagesEl = document.getElementById("messages");
const channelTitleEl = document.getElementById("channelTitle");
const channelMetaEl = document.getElementById("channelMeta");
const statusEl = document.getElementById("status");
const composerEl = document.getElementById("composer");
const bodyEl = document.getElementById("body");
const sendEl = document.getElementById("send");
const fileInputEl = document.getElementById("fileInput");
const attachmentTrayEl = document.getElementById("attachmentTray");
const recordAudioEl = document.getElementById("recordAudio");
const audioRecorderEl = document.getElementById("audioRecorder");
const audioRecorderLabelEl = document.getElementById("audioRecorderLabel");
const audioTimerEl = document.getElementById("audioTimer");
const cancelAudioEl = document.getElementById("cancelAudio");
const finishAudioEl = document.getElementById("finishAudio");

let identities = [];
let channels = [];
let currentIdentity =
  localStorage.getItem("eduvigia_emergency_identity") || "mock:escola-a";
let currentChannelId = null;
let socket = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let generation = 0;
let loadToken = 0;
const seen = new Set();
let selectedFiles = [];
let audioStream = null;
let mediaRecorder = null;
let audioChunks = [];
let audioStartedAt = 0;
let audioTimerHandle = null;
let audioAutoStopHandle = null;
let audioCancelled = false;
const AUDIO_MAX_SECONDS = 60;
const AUDIO_MAX_BYTES = 12 * 1024 * 1024;

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const MAX_FILES = 5;
const MAX_TOTAL_BYTES = 50 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set([
  ".jpg", ".jpeg", ".png", ".webp", ".pdf",
  ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv",
  ".webm", ".ogg", ".m4a"
]);

function friendlyHttpError(status, detail = "") {
  if (status >= 500) {
    return "Não foi possível concluir a operação. Tente novamente.";
  }

  if (status === 403) {
    return "Você não possui permissão para acessar este conteúdo.";
  }

  if (status === 413) {
    return detail || "O arquivo excede o limite permitido.";
  }

  if (status === 415) {
    return detail || "Este tipo de arquivo não é permitido.";
  }

  if (status === 422) {
    return detail || "Os dados enviados não são válidos.";
  }

  if (status === 404) {
    return "O conteúdo solicitado não foi encontrado.";
  }

  return detail || "Não foi possível concluir a operação.";
}

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(
      friendlyHttpError(response.status, payload.detail || "")
    );
    error.status = response.status;
    throw error;
  }

  return response.json();
}

function setStatus(text, online = false) {
  statusEl.textContent = text;
  statusEl.className = online ? "status online" : "status";
}

function identityById(id) {
  return identities.find(item => item.id === id) || null;
}

function currentIdentityObject() {
  return identityById(currentIdentity);
}

function currentChannel() {
  return channels.find(item => item.id === currentChannelId) || null;
}

function isSchoolIdentity() {
  return currentIdentityObject()?.organization_kind === "ESCOLA";
}

// EDUVIGIA_CHAT_BROADCAST_UI_V072
const BROADCAST_CHANNEL_ID = "institutional:ALL-SCHOOLS";

function isBroadcastChannel(channel) {
  return Boolean(
    channel &&
    channel.id === BROADCAST_CHANNEL_ID &&
    channel.type === "INSTITUTIONAL"
  );
}

function canWriteChannel(channel) {
  if (!channel) return false;
  if (!isBroadcastChannel(channel)) return true;

  const kind = currentIdentityObject()?.organization_kind;

  return kind === "GUARDA" || kind === "SECRETARIA";
}

function pttContextChannelId() {
  const channel = currentChannel();

  if (
    !channel ||
    channel.type === "INSTITUTIONAL" ||
    channel.ptt_enabled === false
  ) {
    return null;
  }

  return currentChannelId;
}

function applyChannelMode(channel) {
  const broadcast = isBroadcastChannel(channel);
  const writable = canWriteChannel(channel);

  document.documentElement.dataset.channelMode =
    broadcast ? "broadcast" : "emergency";

  composerEl?.classList.toggle(
    "read-only-channel",
    Boolean(broadcast && !writable)
  );

  if (bodyEl) {
    bodyEl.disabled = !writable;
    bodyEl.placeholder =
      broadcast && !writable
        ? "Canal de avisos gerais - somente leitura para escolas"
        : "Digite uma mensagem ou envie anexos...";
  }

  if (sendEl) sendEl.disabled = !writable;
  if (fileInputEl) fileInputEl.disabled = !writable;

  const pttButton = document.getElementById("pttButton");
  const pttPanel =
    document.getElementById("pttPanel") ||
    document.querySelector(".ptt-panel") ||
    document.querySelector(".ptt-card");
  const pttHistoryPanel = document.getElementById("pttHistoryPanel");
  const pttHistoryToggle = document.getElementById("pttHistoryToggle");

  if (pttButton) pttButton.hidden = broadcast;
  if (pttPanel) pttPanel.hidden = broadcast;
  if (pttHistoryPanel && broadcast) pttHistoryPanel.hidden = true;
  if (pttHistoryToggle) pttHistoryToggle.hidden = broadcast;
}

function channelLabel(channel) {
  if (isBroadcastChannel(channel)) {
    return channel.title || "Avisos Gerais - Todas as Escolas";
  }

  return channel.school_display_name || channel.title || channel.school_code;
}

function renderIdentityInfo() {
  const identity = currentIdentityObject();

  if (!identity) {
    identityInfoEl.textContent = "";
    return;
  }

  if (identity.organization_kind === "ESCOLA") {
    identityInfoEl.textContent =
      `${identity.role} · ${identity.school_code} · acesso somente à própria escola`;
    operatorToolsEl.hidden = true;
    sectionTitleEl.textContent = "Meus Canais Institucionais";
    return;
  }

  identityInfoEl.textContent =
    `${identity.role} · visão operacional das escolas autorizadas`;
  operatorToolsEl.hidden = false;
  sectionTitleEl.textContent = "Canais Institucionais";
}

async function loadIdentities() {
  identities = await jsonFetch("/api/emergency/identities");
  identityEl.innerHTML = "";

  for (const identity of identities) {
    const option = document.createElement("option");
    option.value = identity.id;

    const suffix = identity.school_code
      ? ` · ${identity.school_code}`
      : "";

    option.textContent =
      `${identity.display_name} · ${identity.organization_kind}${suffix}`;

    identityEl.appendChild(option);
  }

  if (!identities.some(item => item.id === currentIdentity)) {
    currentIdentity = identities[0]?.id || "";
  }

  publishChatContext();
  identityEl.value = currentIdentity;
  renderIdentityInfo();
}

function supportsAudioRecording() {
  return Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
}
function preferredAudioMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"];
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported?.(mime)) return mime;
  }
  return "";
}
function audioExtensionForMime(mime) {
  if (mime.includes("ogg")) return ".ogg";
  if (mime.includes("mp4")) return ".m4a";
  return ".webm";
}
function recorderTime(seconds) {
  const safe = Math.max(0, Math.min(AUDIO_MAX_SECONDS, seconds));
  return `${String(Math.floor(safe / 60)).padStart(2,"0")}:${String(safe % 60).padStart(2,"0")}`;
}
function setAudioRecorderVisible(visible) {
  if (audioRecorderEl) audioRecorderEl.hidden = !visible;
}
function stopAudioTracks() {
  if (audioStream) for (const track of audioStream.getTracks()) track.stop();
  audioStream = null;
}
function resetAudioRecorder() {
  if (audioTimerHandle) clearInterval(audioTimerHandle);
  if (audioAutoStopHandle) clearTimeout(audioAutoStopHandle);
  audioTimerHandle = null;
  audioAutoStopHandle = null;
  audioStartedAt = 0;
  audioChunks = [];
  mediaRecorder = null;
  stopAudioTracks();
  setAudioRecorderVisible(false);
  if (audioTimerEl) audioTimerEl.textContent = "00:00";
  if (audioRecorderLabelEl) audioRecorderLabelEl.textContent = "Gravando áudio";
}
async function startAudioRecording() {
  if (!supportsAudioRecording()) { alert("Este navegador não oferece suporte à gravação de áudio."); return; }
  if (!currentChannelId) { alert("Selecione um canal antes de gravar."); return; }
  try {
    audioCancelled = false;
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {echoCancellation:true, noiseSuppression:true, autoGainControl:true}, video:false
    });
    const mimeType = preferredAudioMimeType();
    mediaRecorder = new MediaRecorder(audioStream, mimeType ? {mimeType} : undefined);
    audioChunks = [];
    mediaRecorder.addEventListener("dataavailable", e => { if (e.data?.size > 0) audioChunks.push(e.data); });
    mediaRecorder.addEventListener("stop", () => {
      const recorderMime = mediaRecorder?.mimeType || mimeType || "audio/webm";
      const chunks = [...audioChunks];
      const cancelled = audioCancelled;
      resetAudioRecorder();
      if (cancelled || !chunks.length) return;
      const blob = new Blob(chunks,{type:recorderMime});
      if (!blob.size) { alert("A gravação ficou vazia. Tente novamente."); return; }
      if (blob.size > AUDIO_MAX_BYTES) { alert("A gravação excedeu o limite de 12 MB."); return; }
      const ext = audioExtensionForMime(recorderMime);
      const stamp = new Date().toISOString().replace(/[:.]/g,"-");
      const file = new File([blob],`audio-${stamp}${ext}`,{type:recorderMime});
      try { const merged=[...selectedFiles,file]; validateSelectedFiles(merged); selectedFiles=merged; renderSelectedFiles(); }
      catch (error) { alert(error.message); }
    });
    mediaRecorder.start(500);
    audioStartedAt = Date.now();
    setAudioRecorderVisible(true);
    if (audioTimerEl) audioTimerEl.textContent = "00:00";
    audioTimerHandle = setInterval(() => {
      if (audioTimerEl) audioTimerEl.textContent = recorderTime(Math.floor((Date.now()-audioStartedAt)/1000));
    },250);
    audioAutoStopHandle = setTimeout(() => {
      if (mediaRecorder?.state === "recording") {
        if (audioRecorderLabelEl) audioRecorderLabelEl.textContent = "Limite de 60s atingido";
        mediaRecorder.stop();
      }
    },AUDIO_MAX_SECONDS*1000);
  } catch (error) {
    resetAudioRecorder();
    if (error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError") {
      alert("Permita o acesso ao microfone para gravar uma mensagem de áudio.");
    } else {
      console.error("Falha no microfone:",error);
      alert("Não foi possível iniciar a gravação de áudio.");
    }
  }
}
function finishAudioRecording() { audioCancelled=false; if (mediaRecorder?.state === "recording") mediaRecorder.stop(); }
function cancelAudioRecording() { audioCancelled=true; if (mediaRecorder?.state === "recording") mediaRecorder.stop(); else resetAudioRecorder(); }
function fileExtension(name) {
  const index = String(name || "").lastIndexOf(".");
  return index >= 0 ? String(name).slice(index).toLowerCase() : "";
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function clearSelectedFiles() {
  selectedFiles = [];
  if (fileInputEl) fileInputEl.value = "";
  renderSelectedFiles();
}

function renderSelectedFiles() {
  if (!attachmentTrayEl) return;

  attachmentTrayEl.innerHTML = "";
  attachmentTrayEl.hidden = selectedFiles.length === 0;

  selectedFiles.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "pending-attachment";

    const label = document.createElement("span");
    label.textContent = `${file.name} · ${formatBytes(file.size)}`;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remover";
    remove.addEventListener("click", () => {
      selectedFiles.splice(index, 1);
      renderSelectedFiles();
    });

    item.append(label, remove);
    attachmentTrayEl.appendChild(item);
  });
}

function validateSelectedFiles(files) {
  if (files.length > MAX_FILES) {
    throw new Error("Máximo de 5 anexos por mensagem.");
  }

  let total = 0;

  for (const file of files) {
    const extension = fileExtension(file.name);

    if (!ALLOWED_EXTENSIONS.has(extension)) {
      throw new Error(`Tipo não permitido: ${file.name}`);
    }

    if (file.size <= 0) {
      throw new Error(`Arquivo vazio: ${file.name}`);
    }

    const isAudio = [".webm", ".ogg", ".m4a"].includes(extension);
    if (isAudio && file.size > AUDIO_MAX_BYTES) {
      throw new Error(`Áudio excede 12 MB: ${file.name}`);
    }
    if (!isAudio && file.size > MAX_FILE_BYTES) {
      throw new Error(`Arquivo excede 25 MB: ${file.name}`);
    }

    total += file.size;
  }

  if (total > MAX_TOTAL_BYTES) {
    throw new Error("Os anexos excedem 50 MB por mensagem.");
  }
}

function renderAttachments(message, article) {
  const attachments = Array.isArray(message.attachments) ? message.attachments : [];
  if (!attachments.length) return;
  const list = document.createElement("div");
  list.className = "message-attachments";
  for (const attachment of attachments) {
    const url = `/api/emergency/attachments/${encodeURIComponent(attachment.id)}?identity_id=${encodeURIComponent(currentIdentity)}`;
    const isAudio = String(attachment.mime_type || "").startsWith("audio/") || [".webm",".ogg",".m4a"].includes(String(attachment.extension || "").toLowerCase());
    if (isAudio) {
      const card=document.createElement("div"); card.className="audio-message";
      const head=document.createElement("div"); head.className="audio-message-head";
      const title=document.createElement("strong"); title.textContent="Mensagem de áudio";
      const meta=document.createElement("span"); meta.textContent=formatBytes(attachment.size_bytes);
      head.append(title,meta);
      const player=document.createElement("audio"); player.controls=true; player.preload="metadata"; player.src=url;
      card.append(head,player); list.appendChild(card); continue;
    }
    const link=document.createElement("a"); link.className="message-attachment"; link.href=url; link.target="_blank"; link.rel="noopener";
    const name=document.createElement("strong"); name.textContent=attachment.original_name;
    const meta=document.createElement("span"); meta.textContent=`${attachment.extension.toUpperCase()} · ${formatBytes(attachment.size_bytes)}`;
    link.append(name,meta); list.appendChild(link);
  }
  article.appendChild(list);
}
function publishChatContext() {
  const detail = {
    identityId:
      typeof currentIdentity === "string" && currentIdentity
        ? currentIdentity
        : null,
    channelId: pttContextChannelId()
  };

  window.dispatchEvent(
    new CustomEvent("eduvigia:chat-context", {
      detail
    })
  );

  return detail;
}

window.EduVigIAChatContext = Object.freeze({
  get() {
    return {
      identityId:
        typeof currentIdentity === "string" && currentIdentity
          ? currentIdentity
          : null,
      channelId: pttContextChannelId()
    };
  }
});

function resetChat() {
  currentChannelId = null;
  publishChatContext();
  seen.clear();

  messagesEl.innerHTML =
    '<div class="empty-chat">Selecione um canal de emergência.</div>';

  channelTitleEl.textContent = "Selecione um canal";
  channelMetaEl.textContent =
    "Escola ↔ Guarda Municipal ↔ Secretaria de Educação";

  bodyEl.disabled = true;
  sendEl.disabled = true;
  if (fileInputEl) fileInputEl.disabled = true;
  if (recordAudioEl) recordAudioEl.disabled = true;
  clearSelectedFiles();
}

function filteredChannels() {
  const term = (searchEl?.value || "").trim().toLowerCase();

  if (!term || isSchoolIdentity()) return channels;

  return channels.filter(channel => {
    const source = [
      channel.title,
      channel.school_code,
      channel.school_display_name,
      channel.last_message_body
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return source.includes(term);
  });
}

function renderChannels() {
  const visible = filteredChannels();

  channelsEl.innerHTML = "";
  channelCountEl.textContent = String(visible.length);

  if (!visible.length) {
    const empty = document.createElement("div");
    empty.className = "empty-list";
    empty.textContent = "Nenhum canal encontrado.";
    channelsEl.appendChild(empty);
    return;
  }

  for (const channel of visible) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "channel";
    button.dataset.channelId = channel.id;

    if (isBroadcastChannel(channel)) {
      button.classList.add("broadcast-channel");
    }

    if (channel.id === currentChannelId) {
      button.classList.add("active");
    }

    const top = document.createElement("div");
    top.className = "channel-top";

    const name = document.createElement("strong");
    name.textContent = channelLabel(channel);

    const badge = document.createElement("em");
    const unread = Number(channel.unread_count || 0);
    badge.textContent = unread > 99 ? "99+" : String(unread);
    badge.hidden = unread <= 0;

    top.append(name, badge);

    const school = document.createElement("small");
    school.textContent =
      isBroadcastChannel(channel)
        ? "TODAS AS ESCOLAS - COMUNICADO GERAL"
        : channel.school_code;

    const preview = document.createElement("span");
    preview.textContent =
      channel.last_message_body || "Sem mensagens registradas";

    button.append(top, school, preview);
    button.addEventListener("click", () => selectChannel(channel.id));

    channelsEl.appendChild(button);
  }
}

async function refreshChannels({preserveSelection = true} = {}) {
  const requestGeneration = generation;

  const data = await jsonFetch(
    `/api/emergency/channels?identity_id=${encodeURIComponent(currentIdentity)}`
  );

  if (requestGeneration !== generation) return;

  channels = data;

  // Defense-in-depth in the UI: a school will only keep its own school_code.
  const identity = currentIdentityObject();
  if (identity?.organization_kind === "ESCOLA") {
    channels = channels.filter(
      channel =>
        isBroadcastChannel(channel) ||
        channel.school_code === identity.school_code
    );
  }

  if (
    !preserveSelection ||
    !currentChannelId ||
    !channels.some(item => item.id === currentChannelId)
  ) {
    currentChannelId = channels[0]?.id || null;
  }

  publishChatContext();
  renderChannels();
}

function senderLabel(message) {
  if (message.sender_organization_kind === "ESCOLA") return "ESCOLA";
  if (message.sender_organization_kind === "GUARDA") return "GUARDA";
  if (message.sender_organization_kind === "SECRETARIA") return "SECRETARIA";
  return "SISTEMA";
}

function appendMessage(message) {
  if (!message || seen.has(message.id)) return;
  seen.add(message.id);

  const article = document.createElement("article");
  article.className =
    message.sender_identity_id === currentIdentity
      ? "message own"
      : "message";

  const header = document.createElement("div");
  header.className = "message-header";

  const sender = document.createElement("div");
  sender.className = "sender";

  const institution = document.createElement("span");
  institution.className =
    `institution ${String(message.sender_organization_kind || "").toLowerCase()}`;
  institution.textContent = senderLabel(message);

  const name = document.createElement("strong");
  name.textContent = message.display_name;

  sender.append(institution, name);

  const time = document.createElement("time");
  time.textContent = new Date(message.created_at).toLocaleString();

  const text = document.createElement("div");
  text.className = "message-body";
  text.textContent = message.body;

  header.append(sender, time);
  article.append(header, text);
  renderAttachments(message, article);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function markRead(channelId, messageId) {
  if (!channelId || !messageId) return;

  await jsonFetch(
    `/api/emergency/channels/${encodeURIComponent(channelId)}/read`,
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        identity_id: currentIdentity,
        message_id: messageId
      })
    }
  );
}

async function selectChannel(channelId) {
  const channel = channels.find(item => item.id === channelId);

  if (!channel) {
    resetChat();
    return;
  }

  const identity = currentIdentityObject();

  if (
    identity?.organization_kind === "ESCOLA" &&
    !isBroadcastChannel(channel) &&
    channel.school_code !== identity.school_code
  ) {
    resetChat();
    alert("A escola não possui acesso a este canal.");
    return;
  }

  const token = ++loadToken;
  currentChannelId = channelId;
  applyChannelMode(channel);
  publishChatContext();
  seen.clear();
  messagesEl.innerHTML = "";
  renderChannels();

  channelTitleEl.textContent = channelLabel(channel);
  channelMetaEl.textContent =
    isBroadcastChannel(channel)
      ? (
          canWriteChannel(channel)
            ? "Guarda Municipal / Secretaria -> Todas as escolas - Texto e anexos"
            : "Avisos da Guarda Municipal e Secretaria - Somente leitura"
        )
      : `${channel.school_code} - Escola <-> Guarda Municipal <-> Secretaria de Educacao`;

  bodyEl.disabled = true;
  sendEl.disabled = true;
  if (fileInputEl) fileInputEl.disabled = true;
  if (recordAudioEl) recordAudioEl.disabled = true;
  clearSelectedFiles();

  try {
    const messages = await jsonFetch(
      `/api/emergency/channels/${encodeURIComponent(channelId)}/messages` +
      `?identity_id=${encodeURIComponent(currentIdentity)}&limit=200`
    );

    if (token !== loadToken || currentChannelId !== channelId) return;

    if (!messages.length) {
      messagesEl.innerHTML =
        '<div class="empty-chat">Canal disponível. Nenhuma mensagem registrada.</div>';
    } else {
      messages.forEach(appendMessage);
      await markRead(channelId, messages[messages.length - 1].id);
    }

    const local = channels.find(item => item.id === channelId);
    if (local) local.unread_count = 0;

    renderChannels();

    applyChannelMode(channel);

    if (canWriteChannel(channel)) {
      bodyEl.focus();
    }
  }
  catch (error) {
    if (token !== loadToken) return;

    console.error("Falha ao carregar canal:", error);

    messagesEl.innerHTML =
      '<div class="empty-chat">Não foi possível carregar o histórico deste canal.</div>';

    bodyEl.disabled = true;
    sendEl.disabled = true;
    if (fileInputEl) fileInputEl.disabled = true;
  if (recordAudioEl) recordAudioEl.disabled = true;

    setStatus("erro");
    alert(error.message || "Não foi possível carregar o canal.");
  }
}

function stopSocket() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (heartbeatTimer) clearInterval(heartbeatTimer);

  reconnectTimer = null;
  heartbeatTimer = null;

  if (socket) {
    socket.onclose = null;
    socket.onerror = null;
    socket.onmessage = null;
    socket.close();
    socket = null;
  }
}

function connectSocket() {
  stopSocket();

  const socketGeneration = generation;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";

  socket = new WebSocket(
    `${protocol}//${location.host}/ws?identity_id=${encodeURIComponent(currentIdentity)}`
  );

  socket.onopen = () => {
    if (socketGeneration !== generation) return;

    setStatus("online", true);

    heartbeatTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
    }, 20000);
  };

  socket.onmessage = async event => {
    if (socketGeneration !== generation) return;

    const payload = JSON.parse(event.data);

    if (
      payload.type === "system.ready" ||
      payload.type === "system.pong"
    ) return;

    if (payload.type !== "emergency.message.created") return;

    if (payload.channel_id === currentChannelId) {
      const empty = messagesEl.querySelector(".empty-chat");
      if (empty) empty.remove();

      appendMessage(payload.message);
      await markRead(payload.channel_id, payload.message.id);
    }

    // If another school channel receives a message, Guard/Secretariat
    // receive a refreshed unread badge without marking it as read.
    await refreshChannels({preserveSelection: true});
  };

  socket.onclose = () => {
    if (socketGeneration !== generation) return;

    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = null;

    setStatus("reconectando…");

    reconnectTimer = setTimeout(() => {
      if (socketGeneration === generation) connectSocket();
    }, 1500);
  };

  socket.onerror = () => {
    if (socketGeneration === generation && socket) socket.close();
  };
}

identityEl.addEventListener("change", async () => {
  cancelAudioRecording();
  generation += 1;
  loadToken += 1;

  currentIdentity = identityEl.value;
  publishChatContext();
  localStorage.setItem("eduvigia_emergency_identity", currentIdentity);

  if (searchEl) searchEl.value = "";

  renderIdentityInfo();
  resetChat();
  connectSocket();

  try {
    await refreshChannels({preserveSelection: false});

    if (currentChannelId) {
      await selectChannel(currentChannelId);
    }
  }
  catch (error) {
    console.error(error);
    setStatus("erro");
    alert(error.message);
  }
});

searchEl?.addEventListener("input", renderChannels);

recordAudioEl?.addEventListener("click", startAudioRecording);
finishAudioEl?.addEventListener("click", finishAudioRecording);
cancelAudioEl?.addEventListener("click", cancelAudioRecording);
fileInputEl?.addEventListener("change", () => {
  const incoming = [...(fileInputEl.files || [])];

  try {
    const merged = [...selectedFiles, ...incoming];
    validateSelectedFiles(merged);
    selectedFiles = merged;
    renderSelectedFiles();
  }
  catch (error) {
    fileInputEl.value = "";
    alert(error.message);
  }
});

composerEl.addEventListener("submit", async event => {
  event.preventDefault();

  const channel = currentChannel();
  if (!channel) return;

  const identity = currentIdentityObject();

  if (!canWriteChannel(channel)) {
    alert("Este canal e somente leitura para as escolas.");
    return;
  }

  if (
    identity?.organization_kind === "ESCOLA" &&
    !isBroadcastChannel(channel) &&
    channel.school_code !== identity.school_code
  ) {
    alert("A escola não possui acesso a este canal.");
    return;
  }

  const body = bodyEl.value.trim();

  if (!body && selectedFiles.length === 0) return;

  try {
    validateSelectedFiles(selectedFiles);
  }
  catch (error) {
    alert(error.message);
    return;
  }

  const sentBody = body;
  const sentFiles = [...selectedFiles];

  bodyEl.value = "";
  bodyEl.disabled = true;
  sendEl.disabled = true;
  if (fileInputEl) fileInputEl.disabled = true;
  if (recordAudioEl) recordAudioEl.disabled = true;

  try {
    let message;

    if (sentFiles.length > 0) {
      const form = new FormData();
      form.append("sender_identity_id", currentIdentity);
      form.append("body", sentBody);

      for (const file of sentFiles) {
        form.append("files", file, file.name);
      }

      const response = await fetch(
        `/api/emergency/channels/${encodeURIComponent(channel.id)}/messages-with-attachments`,
        {
          method: "POST",
          body: form
        }
      );

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const error = new Error(
          friendlyHttpError(response.status, payload.detail || "")
        );
        error.status = response.status;
        throw error;
      }

      message = await response.json();
    }
    else {
      message = await jsonFetch(
        `/api/emergency/channels/${encodeURIComponent(channel.id)}/messages`,
        {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            sender_identity_id: currentIdentity,
            body: sentBody
          })
        }
      );
    }

    clearSelectedFiles();

    if (currentChannelId === channel.id) {
      const empty = messagesEl.querySelector(".empty-chat");
      if (empty) empty.remove();

      appendMessage(message);
      await markRead(channel.id, message.id);
    }

    await refreshChannels({preserveSelection: true});
  }
  catch (error) {
    bodyEl.value = sentBody;
    selectedFiles = sentFiles;
    renderSelectedFiles();
    console.error(error);
    alert(error.message);
  }
  finally {
    if (currentChannelId) {
      const activeChannel = currentChannel();
      applyChannelMode(activeChannel);

      if (canWriteChannel(activeChannel)) {
        bodyEl.focus();
      }
    }
  }
});


/*
 * Explicit integration contract for optional frontend modules.
 * Do not make modules depend on lexical globals declared by app.js.
 */
window.EduVigIAChatContext = Object.freeze({
  get() {
    return {
      identityId:
        typeof currentIdentity === "string" && currentIdentity
          ? currentIdentity
          : null,
      channelId: pttContextChannelId()
    };
  }
});
window.addEventListener("beforeunload", () => {
  cancelAudioRecording();
  stopSocket();
});

(async () => {
  try {
    await loadIdentities();

    generation += 1;
    connectSocket();

    await refreshChannels({preserveSelection: false});

    if (currentChannelId) {
      await selectChannel(currentChannelId);
    }
  }
  catch (error) {
    console.error(error);
    setStatus("erro");
    alert(error.message);
  }
})();