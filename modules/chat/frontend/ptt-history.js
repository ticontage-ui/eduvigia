const pttHistoryPanelEl = document.getElementById("pttHistoryPanel");
const pttHistoryToggleEl = document.getElementById("pttHistoryToggle");
const pttHistoryRefreshEl = document.getElementById("pttHistoryRefresh");
const pttHistoryListEl = document.getElementById("pttHistoryList");
const pttHistoryEmptyEl = document.getElementById("pttHistoryEmpty");

let pttHistoryTimer = null;
let pttHistoryOpen = false;

function pttHistoryContext() {
  const publicContext = window.EduVigIAPTT?.getContext?.() || {};

  const identityId =
    publicContext.identityId ||
    document.getElementById("identity")?.value ||
    null;

  const channelId =
    publicContext.channelId ||
    document
      .getElementById("channels")
      ?.querySelector(".channel.active[data-channel-id]")
      ?.dataset?.channelId ||
    null;

  return {
    identityId,
    channelId
  };
}

function pttHistoryEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pttHistoryDuration(ms) {
  const seconds = Math.max(
    0,
    Math.round((Number(ms) || 0) / 1000)
  );

  return `${seconds}s`;
}

function pttHistoryClockFromSeconds(value) {
  const total = Math.max(
    0,
    Math.round(Number(value) || 0)
  );

  const minutes = Math.floor(total / 60);
  const seconds = total % 60;

  return (
    String(minutes).padStart(2, "0") +
    ":" +
    String(seconds).padStart(2, "0")
  );
}

function pttHistoryTimestamp(value) {
  if (!value) return "";

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return parsed.toLocaleString("pt-BR");
}

function pttHistoryAudioUrl(recordingId, identityId) {
  return (
    `/api/ptt/recordings/${encodeURIComponent(recordingId)}` +
    `/audio?identity_id=${encodeURIComponent(identityId)}`
  );
}

function pttCreateHistoryPlayer(item, identityId) {
  const durationSeconds = Math.max(
    0,
    (Number(item.duration_ms) || 0) / 1000
  );

  const player = document.createElement("div");
  player.className = "ptt-history-player";

  const audio = document.createElement("audio");
  audio.className = "ptt-history-audio";
  audio.preload = "metadata";
  audio.src = pttHistoryAudioUrl(item.id, identityId);

  const playButton = document.createElement("button");
  playButton.className = "ptt-history-play";
  playButton.type = "button";
  playButton.textContent = "▶";
  playButton.setAttribute("aria-label", "Reproduzir gravação");

  const currentTime = document.createElement("span");
  currentTime.className = "ptt-history-current";
  currentTime.textContent = "00:00";

  const progress = document.createElement("input");
  progress.className = "ptt-history-progress";
  progress.type = "range";
  progress.min = "0";
  progress.max = String(Math.max(durationSeconds, 0.1));
  progress.step = "0.1";
  progress.value = "0";
  progress.setAttribute("aria-label", "Posição da gravação");

  const totalTime = document.createElement("span");
  totalTime.className = "ptt-history-total";
  totalTime.textContent =
    pttHistoryClockFromSeconds(durationSeconds);

  const muteButton = document.createElement("button");
  muteButton.className = "ptt-history-mute";
  muteButton.type = "button";
  muteButton.textContent = "🔊";
  muteButton.setAttribute("aria-label", "Silenciar gravação");

  function updatePlayer() {
    const current = Number(audio.currentTime) || 0;

    currentTime.textContent =
      pttHistoryClockFromSeconds(current);

    progress.value = String(
      Math.min(
        current,
        durationSeconds || current
      )
    );
  }

  playButton.addEventListener("click", async () => {
    if (audio.paused) {
      try {
        await audio.play();
      } catch (error) {
        console.error("Falha ao reproduzir PTT:", error);
      }
    } else {
      audio.pause();
    }
  });

  audio.addEventListener("play", () => {
    playButton.textContent = "❚❚";
    playButton.setAttribute("aria-label", "Pausar gravação");
  });

  audio.addEventListener("pause", () => {
    playButton.textContent = "▶";
    playButton.setAttribute("aria-label", "Reproduzir gravação");
  });

  audio.addEventListener("timeupdate", updatePlayer);

  audio.addEventListener("ended", () => {
    playButton.textContent = "▶";
    currentTime.textContent = "00:00";
    progress.value = "0";

    try {
      audio.currentTime = 0;
    } catch {}
  });

  progress.addEventListener("input", () => {
    const requested = Number(progress.value) || 0;

    currentTime.textContent =
      pttHistoryClockFromSeconds(requested);

    try {
      audio.currentTime = requested;
    } catch {}
  });

  muteButton.addEventListener("click", () => {
    audio.muted = !audio.muted;
    muteButton.textContent = audio.muted ? "🔇" : "🔊";
    muteButton.setAttribute(
      "aria-label",
      audio.muted ? "Ativar som da gravação" : "Silenciar gravação"
    );
  });

  audio.addEventListener("error", () => {
    player.dataset.error = "true";
    playButton.disabled = true;
    playButton.textContent = "!";
    playButton.setAttribute(
      "aria-label",
      "Não foi possível carregar a gravação"
    );
  });

  player.append(
    playButton,
    currentTime,
    progress,
    totalTime,
    muteButton,
    audio
  );

  return player;
}

async function pttLoadHistory() {
  if (!pttHistoryOpen) return;

  const context = pttHistoryContext();

  if (!context.identityId || !context.channelId) {
    pttHistoryListEl.innerHTML = "";
    pttHistoryEmptyEl.hidden = false;
    pttHistoryEmptyEl.textContent =
      "Selecione um canal para consultar o histórico PTT.";
    return;
  }

  try {
    const response = await fetch(
      `/api/ptt/channels/${encodeURIComponent(context.channelId)}` +
      `/recordings?identity_id=${encodeURIComponent(context.identityId)}` +
      `&limit=50`,
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      let detail = `HTTP ${response.status}`;

      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch {}

      throw new Error(detail);
    }

    const rows = await response.json();

    pttHistoryListEl.innerHTML = "";

    if (!Array.isArray(rows) || !rows.length) {
      pttHistoryEmptyEl.hidden = false;
      pttHistoryEmptyEl.textContent =
        "Nenhuma transmissão gravada neste canal.";
      return;
    }

    pttHistoryEmptyEl.hidden = true;

    for (const item of rows) {
      const article = document.createElement("article");
      article.className = "ptt-history-item";

      const meta = document.createElement("div");
      meta.className = "ptt-history-meta";

      const speaker = document.createElement("strong");
      speaker.textContent =
        item.speaker_display_name ||
        item.speaker_identity_id ||
        "Operador";

      const detail = document.createElement("span");

      const when = pttHistoryTimestamp(item.started_at);
      const duration = pttHistoryDuration(item.duration_ms);

      detail.textContent =
        `${when}${when ? " · " : ""}${duration}`;

      meta.append(
        speaker,
        detail
      );

      const player = pttCreateHistoryPlayer(
        item,
        context.identityId
      );

      article.append(
        meta,
        player
      );

      pttHistoryListEl.appendChild(article);
    }
  } catch (error) {
    console.error("Falha ao carregar histórico PTT:", error);

    pttHistoryListEl.innerHTML = "";
    pttHistoryEmptyEl.hidden = false;
    pttHistoryEmptyEl.textContent =
      error?.message ||
      "Não foi possível carregar o histórico PTT.";
  }
}

function pttSetHistoryOpen(open) {
  pttHistoryOpen = Boolean(open);
  pttHistoryPanelEl.hidden = !pttHistoryOpen;

  if (pttHistoryOpen) {
    pttHistoryToggleEl.textContent = "Fechar histórico";
    pttLoadHistory();

    if (pttHistoryTimer) {
      clearInterval(pttHistoryTimer);
    }

    pttHistoryTimer = setInterval(
      pttLoadHistory,
      5000
    );
  } else {
    pttHistoryToggleEl.textContent = "Histórico PTT";

    if (pttHistoryTimer) {
      clearInterval(pttHistoryTimer);
      pttHistoryTimer = null;
    }
  }
}

pttHistoryToggleEl?.addEventListener(
  "click",
  () => pttSetHistoryOpen(!pttHistoryOpen)
);

pttHistoryRefreshEl?.addEventListener(
  "click",
  pttLoadHistory
);

window.addEventListener(
  "eduvigia:chat-context",
  () => {
    if (pttHistoryOpen) {
      queueMicrotask(pttLoadHistory);
    }
  }
);

window.addEventListener(
  "beforeunload",
  () => {
    if (pttHistoryTimer) {
      clearInterval(pttHistoryTimer);
    }
  }
);

window.EduVigIAPTTHistory = Object.freeze({
  refresh: pttLoadHistory,
  open() {
    pttSetHistoryOpen(true);
  },
  close() {
    pttSetHistoryOpen(false);
  }
});