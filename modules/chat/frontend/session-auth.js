(() => {
  "use strict";

  const MARKER = "EDUVIGIA_CHAT_SESSION_AUTH_V083_R32R3";
  const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  const rawConfig = window.EduVigIAChatConfig || {};
  const apiBase = normalizeBase(rawConfig.apiBase || "/api");
  const wsBase = normalizeBase(rawConfig.wsBase || "/ws");

  let foundation = null;
  let context = null;
  let csrfToken = null;
  let renewalTimer = null;
  let readyPromise = null;

  function normalizeBase(value) {
    const text = String(value || "").trim();
    if (!text || text === "/") return "";
    return (text.startsWith("/") ? text : `/${text}`).replace(/\/+$/, "");
  }

  function apiUrl(path) {
    const value = String(path || "");
    const base = apiBase || "/api";

    if (
      base !== "/api" &&
      (value === base || value.startsWith(`${base}/`))
    ) {
      return value;
    }

    if (value === "/api") return base;
    if (value.startsWith("/api/")) {
      return `${base}${value.slice(4)}`;
    }

    return value;
  }

  function wsPath(path) {
    const value = String(path || "");
    const base = wsBase || "/ws";

    if (
      base !== "/ws" &&
      (value === base || value.startsWith(`${base}/`))
    ) {
      return value;
    }

    if (value === "/ws") return base;
    if (value.startsWith("/ws/")) {
      return `${base}${value.slice(3)}`;
    }

    return value;
  }

  function wsUrl(path, params = {}) {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const search = new URLSearchParams();

    for (const [key, value] of Object.entries(params || {})) {
      if (value === undefined || value === null || value === "") continue;
      search.set(key, String(value));
    }

    const query = search.toString();
    return `${protocol}//${location.host}${wsPath(path)}${query ? `?${query}` : ""}`;
  }

  function isCore() {
    return foundation?.auth_mode === "core";
  }

  function authError(status, detail) {
    const error = new Error(detail || `HTTP ${status}`);
    error.status = status;
    return error;
  }

  async function parseJsonResponse(response) {
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw authError(
        response.status,
        payload.detail || `HTTP ${response.status}`
      );
    }

    return payload;
  }

  function clearContext({notify = false} = {}) {
    context = null;
    csrfToken = null;

    if (renewalTimer) {
      clearTimeout(renewalTimer);
      renewalTimer = null;
    }

    if (notify && isCore()) {
      window.dispatchEvent(
        new CustomEvent("eduvigia:chat-auth-required", {
          detail: {
            authMode: "core"
          }
        })
      );
    }
  }

  function scheduleRenewal(expiresInSeconds) {
    if (!isCore() || !context) return;

    if (renewalTimer) {
      clearTimeout(renewalTimer);
    }

    const ttl = Math.max(60, Number(expiresInSeconds) || 120);
    const delayMs = Math.max(30000, Math.floor(ttl * 500));

    renewalTimer = setTimeout(async () => {
      try {
        await refreshContext();
      } catch (error) {
        console.warn("Chat session renewal failed:", error);
      }
    }, delayMs);
  }

  function applyContext(payload) {
    const previousIdentityId =
      context?.identity?.identity_id ||
      null;

    context = payload || null;
    csrfToken = String(payload?.csrf_token || "");

    if (!context?.identity || !csrfToken) {
      clearContext({notify: true});
      throw authError(
        401,
        "Sessão comercial do Chat incompleta"
      );
    }

    scheduleRenewal(payload.expires_in_seconds);

    const nextIdentityId =
      context.identity.identity_id ||
      null;

    if (previousIdentityId !== nextIdentityId) {
      window.dispatchEvent(
        new CustomEvent("eduvigia:chat-auth-ready", {
          detail: {
            authMode: "core",
            identity: context.identity
          }
        })
      );
    }

    return context;
  }

  async function bootstrap() {
    const response = await fetch(apiUrl("/api/session/foundation"), {
      credentials: "same-origin",
      cache: "no-store"
    });

    foundation = await parseJsonResponse(response);

    if (isCore()) {
      try {
        await refreshContext();
      } catch (error) {
        if (error?.status !== 401) throw error;
      }
    }

    return foundation;
  }

  function ready() {
    if (!readyPromise) {
      readyPromise = bootstrap();
    }

    return readyPromise;
  }

  async function refreshContext() {
    if (!foundation) {
      await ready();
    }

    if (!isCore()) {
      return null;
    }

    const response = await fetch(apiUrl("/api/session/context"), {
      credentials: "same-origin",
      cache: "no-store"
    });

    if (response.status === 401) {
      clearContext({notify: true});
      throw authError(401, "Sessão EduVigIA necessária");
    }

    const payload = await parseJsonResponse(response);
    return applyContext(payload);
  }

  async function exchange(coreBearer) {
    if (!foundation) {
      await ready();
    }

    if (!isCore()) {
      throw authError(
        409,
        "Exchange comercial indisponível em standalone QA"
      );
    }

    const token = String(coreBearer || "").trim();

    if (token.length < 20 || token.length > 4096) {
      throw authError(401, "Token Core inválido");
    }

    const response = await fetch(apiUrl("/api/session/exchange"), {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    const payload = await parseJsonResponse(response);
    return applyContext(payload);
  }

  function withIdentityQuery(path, identityId) {
    const resolved = apiUrl(path);

    if (isCore()) {
      return resolved;
    }

    const value = String(identityId || "").trim();
    if (!value) return resolved;

    const separator = resolved.includes("?") ? "&" : "?";
    return `${resolved}${separator}identity_id=${encodeURIComponent(value)}`;
  }

  function withIdentityPayload(payload, identityId, field = "identity_id") {
    const next = {
      ...(payload || {})
    };

    if (isCore()) {
      delete next[field];
      return next;
    }

    const value = String(identityId || "").trim();
    if (value) {
      next[field] = value;
    }

    return next;
  }

  async function rawFetch(path, options = {}) {
    await ready();

    const method = String(options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});

    if (isCore() && UNSAFE_METHODS.has(method)) {
      if (!csrfToken) {
        await refreshContext();
      }

      headers.set("X-CSRF-Token", csrfToken);
    }

    const response = await fetch(apiUrl(path), {
      ...options,
      method,
      headers,
      credentials: "same-origin"
    });

    if (isCore() && response.status === 401) {
      clearContext({notify: true});
    }

    return response;
  }

  async function api(path, options = {}) {
    const response = await rawFetch(path, options);
    return parseJsonResponse(response);
  }

  async function issueWsTicket(purpose, channelId = null) {
    await ready();

    if (!isCore()) {
      return null;
    }

    const payload = {
      purpose: String(purpose || "").toUpperCase(),
      channel_id: channelId || null
    };

    return api("/api/session/ws-ticket", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }

  async function logout() {
    if (!isCore()) {
      clearContext();
      return {
        ok: true
      };
    }

    if (context) {
      try {
        await api("/api/session/logout", {
          method: "POST"
        });
      } finally {
        clearContext({notify: true});
      }
    } else {
      clearContext({notify: true});
    }

    return {
      ok: true
    };
  }

  function identity() {
    return context?.identity || null;
  }

  function identityId() {
    return identity()?.identity_id || null;
  }

  window.EduVigIAChatAuth = Object.freeze({
    marker: MARKER,
    ready,
    mode() {
      return foundation?.auth_mode || null;
    },
    isCore,
    foundation() {
      return foundation ? {...foundation} : null;
    },
    context() {
      return context ? {...context} : null;
    },
    identity,
    identityId,
    refreshContext,
    exchange,
    logout,
    fetch: rawFetch,
    api,
    apiUrl,
    wsUrl,
    withIdentityQuery,
    withIdentityPayload,
    issueWsTicket
  });

  readyPromise = bootstrap().catch(error => {
    console.error("Chat auth bootstrap failed:", error);
    throw error;
  });
})();