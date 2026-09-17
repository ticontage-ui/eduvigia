(() => {
  "use strict";

  function findSendButton() {
    const preferredForm =
      document.querySelector("#messageForm") ||
      document.querySelector(".message-composer") ||
      document.querySelector(".composer") ||
      document.querySelector("form");

    const selectors = [
      "#sendButton",
      "#sendMessage",
      "button[type='submit']",
      "[data-action='send']",
      "[aria-label='Enviar']",
      "[title='Enviar']"
    ];

    for (const selector of selectors) {
      const candidate =
        preferredForm?.querySelector?.(selector) ||
        document.querySelector(selector);

      if (candidate) return candidate;
    }

    const buttons = Array.from(document.querySelectorAll("button"));

    return (
      buttons.find(button =>
        /^enviar$/i.test(
          String(button.textContent || "").trim()
        )
      ) || null
    );
  }

  function ensureComposerActions(pttButton, sendButton) {
    let actions = document.getElementById("chatComposerActions");

    if (!actions) {
      actions = document.createElement("div");
      actions.id = "chatComposerActions";
      actions.className = "chat-composer-actions";

      sendButton.replaceWith(actions);
      actions.appendChild(pttButton);
      actions.appendChild(sendButton);
    } else {
      if (pttButton.parentElement !== actions) {
        actions.insertBefore(pttButton, actions.firstChild);
      }

      if (sendButton.parentElement !== actions) {
        actions.appendChild(sendButton);
      }
    }

    pttButton.type = "button";
    pttButton.classList.add("ptt-composer-button");
    pttButton.setAttribute(
      "aria-label",
      "Segure para falar no PTT"
    );
    pttButton.setAttribute(
      "title",
      "Segure para falar no PTT"
    );

    sendButton.classList.add("chat-send-button");

    return actions;
  }

  function organizePttStatus(pttButton) {
    const panel =
      document.getElementById("pttPanel") ||
      document.querySelector(".ptt-panel") ||
      document.querySelector(".ptt-card");

    if (!panel) return;

    panel.classList.add("ptt-status-strip");

    const timer = document.getElementById("pttTimer");
    const historyToggle =
      document.getElementById("pttHistoryToggle");

    /*
     * If the timer was nested inside the old large PTT control,
     * move it back to the operational status strip. ptt.js keeps
     * the same DOM reference, so its timer updates continue normally.
     */
    if (
      timer &&
      timer !== pttButton &&
      pttButton.contains(timer)
    ) {
      timer.classList.add("ptt-status-timer");

      if (
        historyToggle &&
        panel.contains(historyToggle)
      ) {
        panel.insertBefore(timer, historyToggle);
      } else {
        panel.appendChild(timer);
      }
    } else if (timer) {
      timer.classList.add("ptt-status-timer");
    }

    /*
     * Visual state only. Existing operational text is never replaced:
     * this lets us keep the current "who is speaking" information.
     */
    function syncVisualState() {
      const text = String(panel.textContent || "")
        .toLowerCase();

      let state = "ready";

      if (
        text.includes("transmitindo") ||
        text.includes("sua voz")
      ) {
        state = "transmitting";
      } else if (
        text.includes("ocupado") ||
        text.includes("está falando") ||
        text.includes("esta falando")
      ) {
        state = "busy";
      } else if (
        text.includes("conectando") ||
        text.includes("reconectando")
      ) {
        state = "connecting";
      } else if (
        text.includes("indisponível") ||
        text.includes("indisponivel")
      ) {
        state = "disabled";
      }

      pttButton.dataset.pttVisualState = state;
      panel.dataset.pttVisualState = state;
    }

    syncVisualState();

    const observer = new MutationObserver(
      syncVisualState
    );

    observer.observe(panel, {
      subtree: true,
      childList: true,
      characterData: true
    });
  }

  function applyPttComposerLayout() {
    const pttButton =
      document.getElementById("pttButton");

    const sendButton =
      findSendButton();

    if (!pttButton || !sendButton) {
      return false;
    }

    ensureComposerActions(
      pttButton,
      sendButton
    );

    organizePttStatus(pttButton);

    document.documentElement.dataset.pttComposerLayout =
      "enabled";

    return true;
  }

  function bootstrap() {
    if (applyPttComposerLayout()) return;

    let attempts = 0;

    const timer = setInterval(() => {
      attempts += 1;

      if (
        applyPttComposerLayout() ||
        attempts >= 30
      ) {
        clearInterval(timer);
      }
    }, 200);
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      bootstrap,
      {once: true}
    );
  } else {
    bootstrap();
  }

  window.EduVigIAPttComposerLayout =
    Object.freeze({
      apply: applyPttComposerLayout
    });
})();