/*
 * EduVigIA Chat Feature Policy
 *
 * Product decision:
 * - text messages: enabled
 * - controlled attachments: enabled
 * - institutional PTT: enabled
 * - PTT recording/history: enabled
 * - asynchronous audio messages: disabled
 *
 * Historical audio data is not deleted by this frontend policy.
 */

(() => {
  "use strict";

  const PTT_SAFE_ROOTS = [
    "#pttPanel",
    ".ptt-panel",
    ".ptt-card",
    "#pttHistoryPanel",
    ".ptt-history-item",
    ".ptt-history-player"
  ].join(",");

  const explicitAsyncAudioSelectors = [
    "#recordAudio",
    "#recordAudioButton",
    "#audioRecord",
    "#audioRecordButton",
    "#audioMessage",
    "#audioMessageButton",
    "#voiceMessage",
    "#voiceMessageButton",
    "#micButton",
    "#microphoneButton",
    "[data-action='record-audio']",
    "[data-action='audio-message']",
    "[data-action='voice-message']",
    "[data-feature='audio-message']",
    "[data-feature='voice-message']"
  ];

  const semanticTerms = [
    "mensagem de áudio",
    "mensagem de audio",
    "gravar áudio",
    "gravar audio",
    "gravação de áudio",
    "gravacao de audio",
    "enviar áudio",
    "enviar audio",
    "voice message",
    "audio message",
    "record audio"
  ];

  function isInsidePtt(element) {
    if (!element || !(element instanceof Element)) return false;

    if (
      element.id?.toLowerCase().startsWith("ptt") ||
      String(element.className || "").toLowerCase().includes("ptt-")
    ) {
      return true;
    }

    return Boolean(element.closest(PTT_SAFE_ROOTS));
  }

  function semanticText(element) {
    return [
      element.id,
      element.className,
      element.getAttribute?.("aria-label"),
      element.getAttribute?.("title"),
      element.getAttribute?.("data-action"),
      element.getAttribute?.("data-feature"),
      element.textContent
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function isAsyncAudioControl(element) {
    if (!element || !(element instanceof Element)) return false;
    if (isInsidePtt(element)) return false;

    if (element.matches(explicitAsyncAudioSelectors.join(","))) {
      return true;
    }

    const isInteractive = element.matches(
      "button, [role='button'], input[type='button'], input[type='file'], a"
    );

    if (!isInteractive) return false;

    const text = semanticText(element);

    return semanticTerms.some(term => text.includes(term));
  }

  function removeAsyncAudioControls(root = document) {
    for (const selector of explicitAsyncAudioSelectors) {
      root.querySelectorAll?.(selector).forEach(element => {
        if (!isInsidePtt(element)) {
          element.remove();
        }
      });
    }

    root
      .querySelectorAll?.(
        "button, [role='button'], input[type='button'], input[type='file'], a"
      )
      .forEach(element => {
        if (isAsyncAudioControl(element)) {
          element.remove();
        }
      });
  }

  function blockUnexpectedAsyncAudioControl(event) {
    const target = event.target?.closest?.(
      "button, [role='button'], input[type='button'], input[type='file'], a"
    );

    if (!target || !isAsyncAudioControl(target)) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    target.remove();
  }

  function applyPolicy() {
    document.documentElement.dataset.asyncAudioMessages = "disabled";
    removeAsyncAudioControls(document);
  }

  document.addEventListener(
    "click",
    blockUnexpectedAsyncAudioControl,
    true
  );

  document.addEventListener(
    "pointerdown",
    blockUnexpectedAsyncAudioControl,
    true
  );

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      applyPolicy,
      {once: true}
    );
  } else {
    applyPolicy();
  }

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) continue;

        if (isAsyncAudioControl(node)) {
          node.remove();
          continue;
        }

        removeAsyncAudioControls(node);
      }
    }
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  window.EduVigIAFeaturePolicy = Object.freeze({
    asyncAudioMessages: false,
    textMessages: true,
    attachments: true,
    institutionalPtt: true,
    pttHistory: true
  });
})();