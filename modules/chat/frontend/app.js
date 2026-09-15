const identityEl = document.getElementById("identity");
const conversationsEl = document.getElementById("conversations");
const messagesEl = document.getElementById("messages");
const titleEl = document.getElementById("conversationTitle");
const metaEl = document.getElementById("conversationMeta");
const statusEl = document.getElementById("status");
const composer = document.getElementById("composer");
const bodyEl = document.getElementById("body");
const sendEl = document.getElementById("send");
const newConversation = document.getElementById("newConversation");
const dialog = document.getElementById("conversationDialog");
const conversationForm = document.getElementById("conversationForm");
const conversationType = document.getElementById("conversationType");
const conversationName = document.getElementById("conversationName");
const memberChoices = document.getElementById("memberChoices");
const cancelDialog = document.getElementById("cancelDialog");

let identities = [];
let conversations = [];
let currentIdentity = localStorage.getItem("eduvigia_chat_identity") || "mock:diego";
let currentConversationId = null;
let socket = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let identityGeneration = 0;
let loadingConversationToken = 0;
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

function currentConversation() {
  return conversations.find(c => c.id === currentConversationId) || null;
}

function conversationLabel(conversation) {
  if (conversation.title) return conversation.title;
  const others = conversation.members.filter(m => m.id !== currentIdentity);
  return others.map(m => m.display_name).join(", ") || "Conversa";
}

function resetConversationView() {
  currentConversationId = null;
  seen.clear();
  messagesEl.innerHTML = "";
  titleEl.textContent = "Selecione uma conversa";
  metaEl.textContent = "Identity Provider: mock Â· Core: desconectado";
  bodyEl.disabled = true;
  sendEl.disabled = true;
}

async function loadIdentities() {
  identities = await jsonFetch("/api/identities");
  identityEl.innerHTML = "";

  for (const identity of identities) {
    const option = document.createElement("option");
    option.value = identity.id;
    option.textContent = `${identity.display_name} Â· ${identity.role}`;
    identityEl.appendChild(option);
  }

  if (!identities.some(i => i.id === currentIdentity)) {
    currentIdentity = identities[0]?.id || "";
  }

  identityEl.value = currentIdentity;
  renderMemberChoices();
}

function renderMemberChoices() {
  memberChoices.innerHTML = "";

  for (const identity of identities) {
    if (identity.id === currentIdentity) continue;

    const label = document.createElement("label");
    label.className = "member-choice";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = identity.id;

    const span = document.createElement("span");
    span.textContent = `${identity.display_name} (${identity.organization_kind})`;

    label.append(input, span);
    memberChoices.appendChild(label);
  }
}

function renderConversations() {
  conversationsEl.innerHTML = "";

  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-list";
    empty.textContent = "Nenhuma conversa.";
    conversationsEl.appendChild(empty);
    return;
  }

  for (const conversation of conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation";

    if (currentConversationId === conversation.id) {
      button.classList.add("active");
    }

    const name = document.createElement("strong");
    name.textContent = conversationLabel(conversation);

    const preview = document.createElement("span");
    preview.textContent = conversation.last_message_body || conversation.type;

    const badge = document.createElement("em");
    const unread = Number(conversation.unread_count || 0);
    badge.textContent = unread > 99 ? "99+" : String(unread);
    badge.hidden = unread <= 0;

    button.append(name, preview, badge);
    button.addEventListener("click", () => selectConversation(conversation.id));
    conversationsEl.appendChild(button);
  }
}

async function refreshConversations({preserveSelection = true} = {}) {
  const generation = identityGeneration;
  const data = await jsonFetch(
    `/api/conversations?identity_id=${encodeURIComponent(currentIdentity)}`
  );

  if (generation !== identityGeneration) return;

  conversations = data;

  if (
    !preserveSelection ||
    !currentConversationId ||
    !conversations.some(c => c.id === currentConversationId)
  ) {
    currentConversationId = conversations[0]?.id || null;
  }

  renderConversations();
}

function appendMessage(message) {
  if (!message || seen.has(message.id)) return;
  seen.add(message.id);

  const row = document.createElement("article");
  row.className = message.sender_identity_id === currentIdentity
    ? "message own"
    : "message";

  const meta = document.createElement("div");
  meta.className = "message-meta";

  const who = document.createElement("strong");
  who.textContent = message.display_name;

  const when = document.createElement("time");
  when.textContent = new Date(message.created_at).toLocaleString();

  const text = document.createElement("div");
  text.className = "message-body";
  text.textContent = message.body;

  meta.append(who, when);
  row.append(meta, text);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function markRead(conversationId, messageId) {
  if (!conversationId || !messageId) return;

  await jsonFetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/read`,
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

async function selectConversation(id) {
  const conversation = conversations.find(c => c.id === id);
  if (!conversation) {
    resetConversationView();
    return;
  }

  const token = ++loadingConversationToken;
  currentConversationId = id;
  seen.clear();
  messagesEl.innerHTML = "";

  renderConversations();

  titleEl.textContent = conversationLabel(conversation);
  metaEl.textContent =
    `${conversation.type} Â· ${conversation.members.map(m => m.display_name).join(", ")}`;

  bodyEl.disabled = true;
  sendEl.disabled = true;

  try {
    const messages = await jsonFetch(
      `/api/conversations/${encodeURIComponent(id)}/messages` +
      `?identity_id=${encodeURIComponent(currentIdentity)}&limit=200`
    );

    if (token !== loadingConversationToken || currentConversationId !== id) return;

    messages.forEach(appendMessage);

    const lastId = messages.length ? messages[messages.length - 1].id : 0;
    if (lastId) {
      await markRead(id, lastId);
    }

    const current = conversations.find(c => c.id === id);
    if (current) current.unread_count = 0;

    renderConversations();

    bodyEl.disabled = false;
    sendEl.disabled = false;
    bodyEl.focus();
  } catch (error) {
    if (token !== loadingConversationToken) return;
    console.error(error);
    resetConversationView();
    alert(error.message);
  }
}

function stopSocket() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }

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

  const generation = identityGeneration;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";

  socket = new WebSocket(
    `${protocol}//${location.host}/ws?identity_id=${encodeURIComponent(currentIdentity)}`
  );

  socket.onopen = () => {
    if (generation !== identityGeneration) return;
    setStatus("online", true);

    heartbeatTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send("ping");
      }
    }, 20000);
  };

  socket.onmessage = async event => {
    if (generation !== identityGeneration) return;

    const payload = JSON.parse(event.data);

    if (payload.type === "system.pong" || payload.type === "system.ready") {
      return;
    }

    if (payload.type === "message.created") {
      if (payload.conversation_id === currentConversationId) {
        appendMessage(payload.message);
        await markRead(payload.conversation_id, payload.message.id);
      }

      await refreshConversations({preserveSelection: true});
      return;
    }

    if (payload.type === "conversation.created") {
      await refreshConversations({preserveSelection: true});
    }
  };

  socket.onclose = () => {
    if (generation !== identityGeneration) return;

    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }

    setStatus("reconectandoâ€¦");

    reconnectTimer = setTimeout(() => {
      if (generation === identityGeneration) connectSocket();
    }, 1500);
  };

  socket.onerror = () => {
    if (generation === identityGeneration && socket) {
      socket.close();
    }
  };
}

identityEl.addEventListener("change", async () => {
  identityGeneration += 1;
  currentIdentity = identityEl.value;
  localStorage.setItem("eduvigia_chat_identity", currentIdentity);

  loadingConversationToken += 1;
  resetConversationView();
  renderMemberChoices();
  connectSocket();

  try {
    await refreshConversations({preserveSelection: false});
    if (currentConversationId) {
      await selectConversation(currentConversationId);
    }
  } catch (error) {
    console.error(error);
    setStatus("erro");
    alert(error.message);
  }
});

composer.addEventListener("submit", async event => {
  event.preventDefault();

  const conversation = currentConversation();
  if (!conversation) return;

  const body = bodyEl.value.trim();
  if (!body) return;

  const sentBody = body;
  bodyEl.value = "";
  bodyEl.disabled = true;
  sendEl.disabled = true;

  try {
    const message = await jsonFetch(
      `/api/conversations/${encodeURIComponent(conversation.id)}/messages`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          sender_identity_id: currentIdentity,
          body: sentBody
        })
      }
    );

    if (currentConversationId === conversation.id) {
      appendMessage(message);
      await markRead(conversation.id, message.id);
    }

    await refreshConversations({preserveSelection: true});
  } catch (error) {
    bodyEl.value = sentBody;
    console.error(error);
    alert(error.message);
  } finally {
    if (currentConversationId) {
      bodyEl.disabled = false;
      sendEl.disabled = false;
      bodyEl.focus();
    }
  }
});

newConversation.addEventListener("click", () => {
  conversationType.value = "DIRECT";
  conversationName.value = "";
  renderMemberChoices();
  dialog.showModal();
});

cancelDialog.addEventListener("click", () => dialog.close());

conversationType.addEventListener("change", () => {
  conversationName.disabled = conversationType.value === "DIRECT";
  if (conversationType.value === "DIRECT") {
    conversationName.value = "";
  }
});

conversationForm.addEventListener("submit", async event => {
  event.preventDefault();

  const memberIds = [...memberChoices.querySelectorAll("input:checked")]
    .map(el => el.value);

  const type = conversationType.value;

  if (type === "DIRECT" && memberIds.length !== 1) {
    alert("Conversa direta exige exatamente um outro membro.");
    return;
  }

  if (type !== "DIRECT" && !conversationName.value.trim()) {
    alert("Informe o tÃ­tulo do grupo.");
    return;
  }

  try {
    const created = await jsonFetch("/api/conversations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        type,
        title: type === "DIRECT" ? null : conversationName.value.trim(),
        created_by: currentIdentity,
        member_ids: memberIds
      })
    });

    dialog.close();

    await refreshConversations({preserveSelection: true});
    await selectConversation(created.id);

    if (created.reused) {
      console.info("Conversa direta existente reutilizada.");
    }
  } catch (error) {
    console.error(error);
    alert(error.message);
  }
});

window.addEventListener("beforeunload", stopSocket);

(async () => {
  try {
    await loadIdentities();

    identityGeneration += 1;
    connectSocket();

    await refreshConversations({preserveSelection: false});

    if (currentConversationId) {
      await selectConversation(currentConversationId);
    }
  } catch (error) {
    console.error(error);
    setStatus("erro");
    alert(error.message);
  }
})();