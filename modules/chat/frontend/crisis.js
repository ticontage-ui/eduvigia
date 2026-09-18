(() => {
  "use strict";

  const MARKER = "EDUVIGIA_CHAT_CRISIS_UI_V080R1";
  const POLL_MS = 5000;

  let identityId = null;
  let context = null;
  let rooms = [];
  let panelOpen = false;
  let pollHandle = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });

    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch (_) {}

      throw new Error(detail);
    }

    return response.status === 204 ? null : response.json();
  }

  function ensureUi() {
    if (document.getElementById("crisisRoomLauncher")) return;

    const launcher = document.createElement("button");
    launcher.id = "crisisRoomLauncher";
    launcher.type = "button";
    launcher.hidden = true;
    launcher.innerHTML = `
      <span class="crisis-dot"></span>
      <span>Sala de Crise</span>
    `;
    launcher.addEventListener("click", () => {
      panelOpen = !panelOpen;
      renderPanelVisibility();
      if (panelOpen) refresh();
    });

    const panel = document.createElement("aside");
    panel.id = "crisisRoomPanel";
    panel.hidden = true;
    panel.innerHTML = `
      <header class="crisis-header">
        <div>
          <strong>Sala de Crise</strong>
          <small id="crisisIdentityLabel">Aguardando identidade...</small>
        </div>
        <button id="crisisClose" type="button" aria-label="Fechar">×</button>
      </header>

      <div id="crisisStatus" class="crisis-status">
        Fundação V0.8-R1 · sem mídia nesta etapa
      </div>

      <div class="crisis-actions">
        <button id="crisisCreate" class="crisis-primary" type="button" hidden>
          Abrir Sala de Crise
        </button>
        <button id="crisisRefresh" type="button">
          Atualizar
        </button>
      </div>

      <div id="crisisRooms" class="crisis-rooms"></div>
    `;

    document.body.appendChild(launcher);
    document.body.appendChild(panel);

    document
      .getElementById("crisisClose")
      .addEventListener("click", () => {
        panelOpen = false;
        renderPanelVisibility();
      });

    document
      .getElementById("crisisRefresh")
      .addEventListener("click", refresh);

    document
      .getElementById("crisisCreate")
      .addEventListener("click", createRoom);
  }

  function renderPanelVisibility() {
    const panel = document.getElementById("crisisRoomPanel");
    if (!panel) return;
    panel.hidden = !panelOpen;
  }

  function updateLauncher() {
    const launcher = document.getElementById("crisisRoomLauncher");
    if (!launcher) return;

    launcher.hidden = !(context && context.can_access);

    if (!context?.can_access) {
      panelOpen = false;
      renderPanelVisibility();
    }
  }

  async function loadContext() {
    if (!identityId) {
      context = null;
      updateLauncher();
      return;
    }

    try {
      context = await api(
        `/api/crisis/context?identity_id=${encodeURIComponent(identityId)}`
      );
    } catch (error) {
      context = null;
    }

    updateLauncher();

    const label = document.getElementById("crisisIdentityLabel");
    if (label) {
      label.textContent = context
        ? `${context.display_name} · ${context.role}`
        : "Sem acesso";
    }

    const create = document.getElementById("crisisCreate");
    if (create) {
      create.hidden = !context?.can_create;
    }
  }

  function statusLabel(status) {
    if (status === "ACTIVE") return "ATIVA";
    if (status === "ENDED") return "ENCERRADA";
    return "PRONTA";
  }

  function renderRooms() {
    const root = document.getElementById("crisisRooms");
    if (!root) return;

    if (!rooms.length) {
      root.innerHTML = `
        <div class="crisis-empty">
          Nenhuma Sala de Crise ativa.
        </div>
      `;
      return;
    }

    root.innerHTML = rooms
      .map(
        room => `
          <article class="crisis-card" data-room-id="${escapeHtml(room.id)}">
            <div class="crisis-card-top">
              <div>
                <strong>${escapeHtml(room.school_code)}</strong>
                <small>${escapeHtml(room.id)}</small>
              </div>
              <span class="crisis-badge ${room.status.toLowerCase()}">
                ${statusLabel(room.status)}
              </span>
            </div>

            <div class="crisis-grid">
              <span>Participantes</span>
              <strong>${Number(room.active_participants || 0)}</strong>

              <span>Áudio escolar</span>
              <strong>${escapeHtml(room.school_audio_state)}</strong>
            </div>

            <div class="crisis-card-actions">
              ${
                room.status !== "ENDED"
                  ? `
                    <button
                      type="button"
                      data-action="join"
                      data-room="${escapeHtml(room.id)}"
                    >
                      Entrar
                    </button>
                    <button
                      type="button"
                      data-action="leave"
                      data-room="${escapeHtml(room.id)}"
                    >
                      Sair
                    </button>
                    <button
                      type="button"
                      data-action="end"
                      data-room="${escapeHtml(room.id)}"
                      class="danger"
                    >
                      Encerrar
                    </button>
                  `
                  : ""
              }
            </div>
          </article>
        `
      )
      .join("");

    root
      .querySelectorAll("[data-action]")
      .forEach(button => {
        button.addEventListener("click", async () => {
          const roomId = button.dataset.room;
          const action = button.dataset.action;
          await roomAction(roomId, action);
        });
      });
  }

  async function refresh() {
    if (!identityId || !context?.can_access) return;

    const status = document.getElementById("crisisStatus");

    try {
      rooms = await api(
        `/api/crisis/rooms?identity_id=${encodeURIComponent(identityId)}`
      );
      renderRooms();

      if (status) {
        status.textContent =
          "V0.8-R1 · lifecycle e RBAC ativos · mídia entra na R2";
      }
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  }

  async function createRoom() {
    if (!identityId || !context?.can_create) return;

    const button = document.getElementById("crisisCreate");
    if (button) button.disabled = true;

    try {
      await api("/api/crisis/rooms", {
        method: "POST",
        body: JSON.stringify({
          identity_id: identityId
        })
      });

      await refresh();
    } catch (error) {
      alert(`Sala de Crise: ${error.message}`);
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function roomAction(roomId, action) {
    if (!identityId) return;

    try {
      await api(
        `/api/crisis/rooms/${encodeURIComponent(roomId)}/${action}`,
        {
          method: "POST",
          body: JSON.stringify({
            identity_id: identityId
          })
        }
      );

      await refresh();
    } catch (error) {
      alert(`Sala de Crise: ${error.message}`);
    }
  }

  async function setIdentity(nextIdentityId) {
    if (identityId === nextIdentityId) return;

    identityId = nextIdentityId || null;
    context = null;
    rooms = [];

    await loadContext();

    if (panelOpen) {
      await refresh();
    }
  }

  function readChatContext() {
    try {
      return window.EduVigIAChatContext?.get?.() || {};
    } catch (_) {
      return {};
    }
  }

  ensureUi();
  void setIdentity(readChatContext().identityId || null);

  window.addEventListener("eduvigia:chat-context", event => {
    void setIdentity(event.detail?.identityId || null);
  });

  pollHandle = window.setInterval(() => {
    if (panelOpen && identityId && context?.can_access) {
      void refresh();
    }
  }, POLL_MS);

  window.addEventListener("beforeunload", () => {
    if (pollHandle) clearInterval(pollHandle);
  });

  window.EduVigIACrisisRoom = Object.freeze({
    marker: MARKER,
    refresh
  });
})();
