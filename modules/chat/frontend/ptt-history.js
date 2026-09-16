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

      const speaker = pttHistoryEscape(
        item.speaker_display_name ||
        item.speaker_identity_id
      );

      const when = pttHistoryEscape(
        pttHistoryTimestamp(item.started_at)
      );

      const duration = pttHistoryEscape(
        pttHistoryDuration(item.duration_ms)
      );

      const digest = pttHistoryEscape(
        (item.sha256 || "").slice(0, 12)
      );

      article.innerHTML = `
        <div class="ptt-history-meta">
          <strong>${speaker}</strong>
          <span>${when} · ${duration}</span>
          <small>SHA-256 ${digest}…</small>
        </div>
        <audio
          controls
          preload="metadata"
          src="${pttHistoryAudioUrl(item.id, context.identityId)}"
        ></audio>
      `;

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