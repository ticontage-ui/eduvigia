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
let currentConversation = null;
let socket = null;
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

function conversationLabel(conversation) {
  if (conversation.title) return conversation.title;
  const others = conversation.members.filter(m => m.id !== currentIdentity);
  return others.map(m => m.display_name).join(", ") || "Conversa";
}

async function loadConversations(selectId = null) {
  conversations = await jsonFetch(
    `/api/conversations?identity_id=${encodeURIComponent(currentIdentity)}`
  );

  conversationsEl.innerHTML = "";

  for (const conversation of conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "conversation";
    if (currentConversation?.id === conversation.id) {
      button.classList.add("active");
    }

    const name = document.createElement("strong");
    name.textContent = conversationLabel(conversation);

    const info = document.createElement("span");
    info.textContent = conversation.type;

    const badge = document.createElement("em");
    badge.textContent = conversation.unread_count > 0
      ? String(conversation.unread_count)
      : "";
    badge.hidden = conversation.unread_count <= 0;

    button.append(name, info, badge);
    button.addEventListener("click", () => openConversation(conversation.id));
    conversationsEl.appendChild(button);
  }

  const wanted = selectId || currentConversation?.id;
  if (wanted && conversations.some(c => c.id === wanted)) {
    await openConversation(wanted, false);
  } else if (conversations.length && !currentConversation) {
    await openConversation(conversations[0].id, false);
  }
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

async function markCurrentRead() {
  if (!currentConversation) return;

  const ids = [...seen];
  if (!ids.length) return;
  const maxId = Math.max(...ids);

  await jsonFetch(
    `/api/conversations/${encodeURIComponent(currentConversation.id)}/read`,
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        identity_id: currentIdentity,
        message_id: maxId
      })
    }
  );
}

async function openConversation(id, reloadList = true) {
  const conversation = conversations.find(c => c.id === id);
  if (!conversation) return;

  currentConversation = conversation;
  seen.clear();
  messagesEl.innerHTML = "";

  titleEl.textContent = conversationLabel(conversation);
  metaEl.textContent =
    `${conversation.type} Â· ${conversation.members.map(m => m.display_name).join(", ")}`;

  bodyEl.disabled = false;
  sendEl.disabled = false;

  const messages = await jsonFetch(
    `/api/conversations/${encodeURIComponent(id)}/messages` +
    `?identity_id=${encodeURIComponent(currentIdentity)}&limit=200`
  );

  messages.forEach(appendMessage);
  await markCurrentRead();

  if (reloadList) {
    await loadConversations(id);
  }
}

function connectSocket() {
  if (socket) {
    socket.onclose = null;
    socket.close();
  }

  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(
    `${protocol}//${location.host}/ws?identity_id=${encodeURIComponent(currentIdentity)}`
  );

  socket.onopen = () => setStatus("online", true);

  socket.onmessage = async event => {
    const payload = JSON.parse(event.data);

    if (payload.type === "message.created") {
      if (currentConversation?.id === payload.conversation_id) {
        appendMessage(payload.message);
        await markCurrentRead();
      }
      await loadConversations(currentConversation?.id || null);
    }

    if (payload.type === "conversation.created") {
      await loadConversations(payload.conversation_id);
    }
  };

  socket.onclose = () => {
    setStatus("reconectandoâ€¦");
    setTimeout(connectSocket, 2000);
  };

  socket.onerror = () => socket.close();
}

identityEl.addEventListener("change", async () => {
  currentIdentity = identityEl.value;
  localStorage.setItem("eduvigia_chat_identity", currentIdentity);
  currentConversation = null;
  bodyEl.disabled = true;
  sendEl.disabled = true;
  messagesEl.innerHTML = "";
  renderMemberChoices();
  connectSocket();
  await loadConversations();
});

composer.addEventListener("submit", async event => {
  event.preventDefault();
  if (!currentConversation) return;

  const body = bodyEl.value.trim();
  if (!body) return;

  const message = await jsonFetch(
    `/api/conversations/${encodeURIComponent(currentConversation.id)}/messages`,
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        sender_identity_id: currentIdentity,
        body
      })
    }
  );

  appendMessage(message);
  bodyEl.value = "";
  bodyEl.focus();
  await markCurrentRead();
  await loadConversations(currentConversation.id);
});

newConversation.addEventListener("click", () => {
  conversationType.value = "DIRECT";
  conversationName.value = "";
  renderMemberChoices();
  dialog.showModal();
});

cancelDialog.addEventListener("click", () => dialog.close());

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
  await loadConversations(created.id);
});

(async () => {
  try {
    await loadIdentities();
    connectSocket();
    await loadConversations();
  } catch (error) {
    console.error(error);
    setStatus("erro");
    alert(error.message);
  }
})();