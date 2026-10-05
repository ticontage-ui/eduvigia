(() => {
  "use strict";

  const MARKER = "EDUVIGIA_CHAT_CORE_BRIDGE_V083_R522";
  const CORE_TOKEN_KEY = "eduvigia_token";

  window.EduVigIAChatConfig = Object.freeze({
    apiBase: "/api/chat",
    wsBase: "/ws/chat",
    rtcBase: "/rtc/chat",
    coreShellUrl: "/"
  });

  let exchangePromise = null;
  let redirecting = false;

  function coreShellUrl(reason = "") {
    const target = new URL(
      window.EduVigIAChatConfig.coreShellUrl || "/",
      window.location.origin
    );

    if (reason) {
      target.searchParams.set("chat_auth", reason);
    }

    return target.toString();
  }

  function returnToCore(reason) {
    if (redirecting) return;
    redirecting = true;
    window.location.replace(coreShellUrl(reason));
  }

  function readCoreBearer() {
    return String(
      window.localStorage.getItem(CORE_TOKEN_KEY) || ""
    ).trim();
  }

  async function ensureCommercialSession() {
    const auth = window.EduVigIAChatAuth;

    if (!auth?.ready || !auth?.exchange) {
      throw new Error(
        "Adaptador de sessão do Chat indisponível"
      );
    }

    await auth.ready();

    if (!auth.isCore()) {
      return {
        authMode: auth.mode?.() || "standalone_qa",
        exchanged: false
      };
    }

    if (auth.identity?.()) {
      return {
        authMode: "core",
        exchanged: false,
        context: auth.context?.() || null
      };
    }

    let coreBearer = readCoreBearer();

    if (!coreBearer) {
      returnToCore("missing-core-session");
      return null;
    }

    try {
      const context = await auth.exchange(coreBearer);

      return {
        authMode: "core",
        exchanged: true,
        context
      };
    }
    catch (error) {
      window.dispatchEvent(
        new CustomEvent("eduvigia:chat-core-bridge-failed", {
          detail: {
            status: Number(error?.status || 0),
            message: String(
              error?.message ||
              "Falha ao iniciar sessão de Comunicação"
            )
          }
        })
      );

      if (
        Number(error?.status || 0) === 401 ||
        Number(error?.status || 0) === 403
      ) {
        returnToCore("invalid-core-session");
      }

      throw error;
    }
    finally {
      coreBearer = "";
    }
  }

  function run() {
    if (exchangePromise) {
      return exchangePromise;
    }

    exchangePromise = ensureCommercialSession()
      .catch(error => {
        console.error("Core → Chat session bridge failed:", error);
        throw error;
      })
      .finally(() => {
        exchangePromise = null;
      });

    return exchangePromise;
  }

  window.addEventListener(
    "eduvigia:chat-auth-required",
    () => {
      void run().catch(() => {});
    }
  );

  window.addEventListener(
    "DOMContentLoaded",
    () => {
      void run().catch(() => {});
    },
    {once: true}
  );

  window.EduVigIAChatCoreBridge = Object.freeze({
    marker: MARKER,
    run
  });
})();
