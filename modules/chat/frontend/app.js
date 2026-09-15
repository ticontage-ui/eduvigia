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

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
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

function channelLabel(channel) {
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
    sectionTitleEl.textContent = "Meu Canal de Emergência";
    return;
  }

  identityInfoEl.textContent =
    `${identity.role} · visão operacional das escolas autorizadas`;
  operatorToolsEl.hidden = false;
  sectionTitleEl.textContent = "Canais das Escolas";
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

  identityEl.value = currentIdentity;
  renderIdentityInfo();
}

function resetChat() {
  currentChannelId = null;
  seen.clear();

  messagesEl.innerHTML =
    '<div class="empty-chat">Selecione um canal de emergência.</div>';

  channelTitleEl.textContent = "Selecione um canal";
  channelMetaEl.textContent =
    "Escola ↔ Guarda Municipal ↔ Secretaria de Educação";

  bodyEl.disabled = true;
  sendEl.disabled = true;
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
    school.textContent = channel.school_code;

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
      channel => channel.school_code === identity.school_code
    );
  }

  if (
    !preserveSelection ||
    !currentChannelId ||
    !channels.some(item => item.id === currentChannelId)
  ) {
    currentChannelId = channels[0]?.id || null;
  }

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
    channel.school_code !== identity.school_code
  ) {
    resetChat();
    alert("A escola não possui acesso a este canal.");
    return;
  }

  const token = ++loadToken;
  currentChannelId = channelId;
  seen.clear();
  messagesEl.innerHTML = "";
  renderChannels();

  channelTitleEl.textContent = channelLabel(channel);
  channelMetaEl.textContent =
    `${channel.school_code} · Escola ↔ Guarda Municipal ↔ Secretaria de Educação`;

  bodyEl.disabled = true;
  sendEl.disabled = true;

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

    bodyEl.disabled = false;
    sendEl.disabled = false;
    bodyEl.focus();
  }
  catch (error) {
    if (token !== loadToken) return;
    console.error(error);
    resetChat();
    alert(error.message);
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
  generation += 1;
  loadToken += 1;

  currentIdentity = identityEl.value;
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

composerEl.addEventListener("submit", async event => {
  event.preventDefault();

  const channel = currentChannel();
  if (!channel) return;

  const identity = currentIdentityObject();

  if (
    identity?.organization_kind === "ESCOLA" &&
    channel.school_code !== identity.school_code
  ) {
    alert("A escola não possui acesso a este canal.");
    return;
  }

  const body = bodyEl.value.trim();
  if (!body) return;

  bodyEl.value = "";
  bodyEl.disabled = true;
  sendEl.disabled = true;

  try {
    const message = await jsonFetch(
      `/api/emergency/channels/${encodeURIComponent(channel.id)}/messages`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          sender_identity_id: currentIdentity,
          body
        })
      }
    );

    if (currentChannelId === channel.id) {
      const empty = messagesEl.querySelector(".empty-chat");
      if (empty) empty.remove();

      appendMessage(message);
      await markRead(channel.id, message.id);
    }

    await refreshChannels({preserveSelection: true});
  }
  catch (error) {
    bodyEl.value = body;
    console.error(error);
    alert(error.message);
  }
  finally {
    if (currentChannelId) {
      bodyEl.disabled = false;
      sendEl.disabled = false;
      bodyEl.focus();
    }
  }
});

window.addEventListener("beforeunload", stopSocket);

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