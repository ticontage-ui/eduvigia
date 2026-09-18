(() => {
  "use strict";

  const MARKER = "EDUVIGIA_CHAT_CRISIS_LIVE_AUDIO_V0822";
  const LK = window.LivekitClient;
  const sessions = new Map();

  let identityId = null;
  let context = null;
  let decorating = false;
  let decorateTimer = null;

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

  function readIdentity() {
    try {
      return window.EduVigIAChatContext?.get?.()?.identityId || null;
    } catch (_) {
      return null;
    }
  }

  async function loadContext() {
    identityId = readIdentity();

    if (!identityId) {
      context = null;
      return;
    }

    try {
      context = await api(
        `/api/crisis/context?identity_id=${encodeURIComponent(identityId)}`
      );
    } catch (_) {
      context = null;
    }
  }

  function sessionFor(roomId) {
    return sessions.get(roomId) || null;
  }

  function setSession(roomId, session) {
    sessions.set(roomId, session);
    scheduleDecorate();
  }

  function clearSession(roomId) {
    sessions.delete(roomId);
    scheduleDecorate();
  }

  async function tokenFor(roomId) {
    return api(
      `/api/crisis/rooms/${encodeURIComponent(roomId)}/media/token`,
      {
        method: "POST",
        body: JSON.stringify({ identity_id: identityId })
      }
    );
  }

  async function setState(roomId, state) {
    return api(
      `/api/crisis/rooms/${encodeURIComponent(roomId)}/media/state`,
      {
        method: "POST",
        body: JSON.stringify({
          identity_id: identityId,
          state
        })
      }
    );
  }

  function mediaHost(card) {
    let host = card.querySelector(".crisis-live-audio");
    if (!host) {
      host = document.createElement("div");
      host.className = "crisis-live-audio";
      card.appendChild(host);
    }
    return host;
  }

  function ensureAudioSink(roomId, host) {
    let sink = host.querySelector(".crisis-remote-audio");
    if (!sink) {
      sink = document.createElement("div");
      sink.className = "crisis-remote-audio";
      sink.dataset.roomId = roomId;
      host.appendChild(sink);
    }
    return sink;
  }

  function renderSessionStatus(host, text, kind = "") {
    let status = host.querySelector(".crisis-media-status");
    if (!status) {
      status = document.createElement("div");
      status.className = "crisis-media-status";
      host.prepend(status);
    }
    status.className = `crisis-media-status ${kind}`.trim();
    status.textContent = text;
  }

  async function startManagerLive(room) {
    if (!window.isSecureContext) {
      throw new Error(
        "Áudio LIVE exige HTTPS. Acesse o Chat pelo endereço HTTPS da Sala de Crise."
      );
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Este navegador não disponibiliza captura segura de microfone.");
    }

    if (!LK?.Room) {
      throw new Error("LiveKit Client não carregado.");
    }

    const existing = sessionFor(room.id);
    if (existing) return;

    const token = await tokenFor(room.id);
    const lkRoom = new LK.Room({
      autoSubscribe: false,
      adaptiveStream: false,
      dynacast: false
    });

    lkRoom.on(LK.RoomEvent.Reconnecting, () => scheduleDecorate());
    lkRoom.on(LK.RoomEvent.Reconnected, () => scheduleDecorate());
    lkRoom.on(LK.RoomEvent.Disconnected, () => {
      const current = sessionFor(room.id);
      if (current?.room === lkRoom) {
        clearSession(room.id);
      }
    });

    try {
      await lkRoom.connect(token.server_url, token.token, {
        autoSubscribe: false
      });

      await lkRoom.localParticipant.setMicrophoneEnabled(true, {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      });

      await setState(room.id, "LIVE");

      setSession(room.id, {
        role: "publisher",
        room: lkRoom,
        connectedAt: Date.now()
      });
    } catch (error) {
      try {
        await lkRoom.localParticipant.setMicrophoneEnabled(false);
      } catch (_) {}

      try {
        lkRoom.disconnect();
      } catch (_) {}

      try {
        await setState(room.id, "OFF");
      } catch (_) {}

      throw error;
    }
  }

  async function stopManagerLive(roomId) {
    const session = sessionFor(roomId);

    if (session?.room) {
      try {
        await session.room.localParticipant.setMicrophoneEnabled(false);
      } catch (_) {}

      try {
        session.room.disconnect();
      } catch (_) {}
    }

    try {
      await setState(roomId, "OFF");
    } finally {
      clearSession(roomId);
    }
  }

  async function connectOperator(room) {
    if (!LK?.Room) {
      throw new Error("LiveKit Client não carregado.");
    }

    if (sessionFor(room.id)) return;

    const token = await tokenFor(room.id);
    const lkRoom = new LK.Room({
      autoSubscribe: true,
      adaptiveStream: false,
      dynacast: false
    });

    const card = document.querySelector(
      `.crisis-card[data-room-id="${CSS.escape(room.id)}"]`
    );
    const host = card ? mediaHost(card) : document.body;
    const sink = card ? ensureAudioSink(room.id, host) : document.body;

    lkRoom.on(
      LK.RoomEvent.TrackSubscribed,
      (track, publication, participant) => {
        if (track.kind !== LK.Track.Kind.Audio) return;

        const element = track.attach();
        element.autoplay = true;
        element.dataset.crisisRemoteAudio = room.id;
        sink.appendChild(element);
        scheduleDecorate();
      }
    );

    lkRoom.on(
      LK.RoomEvent.TrackUnsubscribed,
      track => {
        for (const element of track.detach()) {
          element.remove();
        }
        scheduleDecorate();
      }
    );

    lkRoom.on(LK.RoomEvent.AudioPlaybackStatusChanged, () => {
      scheduleDecorate();
    });

    lkRoom.on(LK.RoomEvent.Reconnecting, () => scheduleDecorate());
    lkRoom.on(LK.RoomEvent.Reconnected, () => scheduleDecorate());
    lkRoom.on(LK.RoomEvent.Disconnected, () => {
      const current = sessionFor(room.id);
      if (current?.room === lkRoom) clearSession(room.id);
    });

    await lkRoom.connect(token.server_url, token.token, {
      autoSubscribe: true
    });

    setSession(room.id, {
      role: "subscriber",
      room: lkRoom,
      connectedAt: Date.now()
    });
  }

  async function disconnectOperator(roomId) {
    const session = sessionFor(roomId);
    if (session?.room) {
      try {
        session.room.disconnect();
      } catch (_) {}
    }
    clearSession(roomId);
  }

  async function joinedByMe(roomId) {
    if (!identityId) return false;

    try {
      const detail = await api(
        `/api/crisis/rooms/${encodeURIComponent(roomId)}?identity_id=${encodeURIComponent(identityId)}`
      );

      return Boolean(
        detail.participants?.some(
          participant =>
            participant.identity_id === identityId &&
            !participant.left_at
        )
      );
    } catch (_) {
      return false;
    }
  }

  async function roomList() {
    if (!identityId || !context?.can_access) return [];

    return api(
      `/api/crisis/rooms?identity_id=${encodeURIComponent(identityId)}`
    );
  }

  function operatorPlaybackButton(host, roomId, lkRoom) {
    let button = host.querySelector(".crisis-start-playback");

    if (lkRoom.canPlaybackAudio) {
      button?.remove();
      return;
    }

    if (!button) {
      button = document.createElement("button");
      button.type = "button";
      button.className = "crisis-start-playback";
      button.textContent = "Ativar som no navegador";
      button.addEventListener("click", async () => {
        try {
          await lkRoom.startAudio();
          button.remove();
          scheduleDecorate();
        } catch (error) {
          alert(`Sala de Crise: ${error.message}`);
        }
      });
      host.appendChild(button);
    }
  }

  async function decorateCards() {
    if (decorating) return;
    decorating = true;

    try {
      await loadContext();

      if (!context?.can_access) return;

      const rooms = await roomList();
      const byId = new Map(rooms.map(room => [room.id, room]));

      document
        .querySelectorAll(".crisis-card[data-room-id]")
        .forEach(card => {
          const roomId = card.dataset.roomId;
          const room = byId.get(roomId);
          if (!room) return;

          const host = mediaHost(card);
          const existingControls = host.querySelector(".crisis-media-controls");
          existingControls?.remove();

          const controls = document.createElement("div");
          controls.className = "crisis-media-controls";

          const session = sessionFor(roomId);

          if (context.can_publish_school_audio) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "crisis-live-toggle";

            if (session?.role === "publisher") {
              button.classList.add("is-live");
              button.textContent = "Parar transmissão";
              renderSessionStatus(host, "Áudio escolar: AO VIVO", "live");

              button.addEventListener("click", async () => {
                button.disabled = true;
                try {
                  await stopManagerLive(roomId);
                  await window.EduVigIACrisisRoom?.refresh?.();
                } catch (error) {
                  alert(`Sala de Crise: ${error.message}`);
                } finally {
                  button.disabled = false;
                }
              });
            } else {
              button.textContent = "Transmitir áudio";
              renderSessionStatus(
                host,
                room.school_audio_state === "LIVE"
                  ? "Áudio escolar: LIVE em outra sessão"
                  : "Áudio escolar: desligado",
                room.school_audio_state === "LIVE" ? "live" : ""
              );

              button.addEventListener("click", async () => {
                button.disabled = true;
                try {
                  await startManagerLive(room);
                  await window.EduVigIACrisisRoom?.refresh?.();
                } catch (error) {
                  alert(`Sala de Crise: ${error.message}`);
                } finally {
                  button.disabled = false;
                }
              });
            }

            if (room.status !== "ENDED") controls.appendChild(button);
          } else {
            if (session?.role === "subscriber") {
              renderSessionStatus(
                host,
                room.school_audio_state === "LIVE"
                  ? "Conectado · ouvindo áudio escolar"
                  : "Conectado · aguardando áudio escolar",
                room.school_audio_state === "LIVE" ? "live" : "waiting"
              );

              operatorPlaybackButton(host, roomId, session.room);
            } else {
              renderSessionStatus(
                host,
                room.school_audio_state === "LIVE"
                  ? "Áudio escolar LIVE · entre na sala para ouvir"
                  : "Áudio escolar: desligado",
                room.school_audio_state === "LIVE" ? "live" : ""
              );
            }
          }

          host.appendChild(controls);
        });
    } catch (error) {
      console.warn("Crisis media decorate failed", error);
    } finally {
      decorating = false;
    }
  }

  function scheduleDecorate() {
    window.clearTimeout(decorateTimer);
    decorateTimer = window.setTimeout(() => {
      void decorateCards();
    }, 120);
  }

  async function autoConnectAfterJoin(roomId) {
    await new Promise(resolve => window.setTimeout(resolve, 450));
    await loadContext();

    if (!context?.can_access || context?.can_publish_school_audio) return;

    const rooms = await roomList();
    const room = rooms.find(candidate => candidate.id === roomId);
    if (!room || room.status === "ENDED") return;

    try {
      await connectOperator(room);
    } catch (error) {
      alert(`Sala de Crise — áudio: ${error.message}`);
    }

    scheduleDecorate();
  }

  document.addEventListener(
    "click",
    event => {
      const button = event.target.closest("[data-action][data-room]");
      if (!button) return;

      const action = button.dataset.action;
      const roomId = button.dataset.room;
      if (!roomId) return;

      if (action === "join") {
        void autoConnectAfterJoin(roomId);
      }

      if (action === "leave" || action === "end") {
        void disconnectOperator(roomId);
      }
    },
    true
  );

  const observer = new MutationObserver(scheduleDecorate);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  window.addEventListener("eduvigia:chat-context", async () => {
    for (const [roomId, session] of sessions.entries()) {
      try {
        if (session.role === "publisher") {
          await session.room.localParticipant.setMicrophoneEnabled(false);
        }
        session.room.disconnect();
      } catch (_) {}
      sessions.delete(roomId);
    }

    await loadContext();
    scheduleDecorate();
  });

  window.addEventListener("beforeunload", () => {
    for (const [roomId, session] of sessions.entries()) {
      if (session.role === "publisher" && identityId) {
        try {
          fetch(
            `/api/crisis/rooms/${encodeURIComponent(roomId)}/media/state`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                identity_id: identityId,
                state: "OFF"
              }),
              keepalive: true
            }
          );
        } catch (_) {}
      }

      try {
        session.room.disconnect();
      } catch (_) {}
    }
  });

  if (!LK?.Room) {
    console.error("LiveKit Client SDK missing.");
  }

  void loadContext().then(scheduleDecorate);

  window.EduVigIACrisisMedia = Object.freeze({
    marker: MARKER,
    refresh: scheduleDecorate
  });
})();
