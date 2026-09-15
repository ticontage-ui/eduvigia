const messagesEl = document.getElementById("messages");
const form = document.getElementById("form");
const bodyEl = document.getElementById("body");
const nameEl = document.getElementById("displayName");
const statusEl = document.getElementById("status");

const seen = new Set();

const savedName = localStorage.getItem("eduvigia_chat_dev_name");
if (savedName) nameEl.value = savedName;

nameEl.addEventListener("change", () => {
  localStorage.setItem("eduvigia_chat_dev_name", nameEl.value.trim());
});

function appendMessage(message) {
  if (!message || seen.has(message.id)) return;
  seen.add(message.id);

  const row = document.createElement("article");
  row.className = "message";

  const meta = document.createElement("div");
  meta.className = "meta";

  const who = document.createElement("strong");
  who.textContent = message.display_name;

  const when = document.createElement("time");
  when.textContent = new Date(message.created_at).toLocaleString();

  const text = document.createElement("div");
  text.className = "text";
  text.textContent = message.body;

  meta.append(who, when);
  row.append(meta, text);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function loadHistory() {
  const response = await fetch("/api/messages?room_id=general&limit=100");
  if (!response.ok) throw new Error("Falha ao carregar historico");
  const messages = await response.json();
  messages.forEach(appendMessage);
}

let socket;

function connectSocket() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${location.host}/ws`);

  socket.onopen = () => {
    statusEl.textContent = "online";
    statusEl.className = "status online";
  };

  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "message.created") {
      appendMessage(payload.message);
    }
  };

  socket.onclose = () => {
    statusEl.textContent = "reconectandoâ€¦";
    statusEl.className = "status";
    setTimeout(connectSocket, 2000);
  };

  socket.onerror = () => socket.close();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const displayName = nameEl.value.trim();
  const body = bodyEl.value.trim();

  if (!displayName || !body) return;

  localStorage.setItem("eduvigia_chat_dev_name", displayName);

  const response = await fetch("/api/messages", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      room_id: "general",
      display_name: displayName,
      body
    })
  });

  if (!response.ok) {
    alert("Falha ao enviar a mensagem.");
    return;
  }

  const message = await response.json();
  appendMessage(message);
  bodyEl.value = "";
  bodyEl.focus();
});

(async () => {
  try {
    await loadHistory();
    connectSocket();
  } catch (error) {
    statusEl.textContent = "erro";
    console.error(error);
  }
})();
