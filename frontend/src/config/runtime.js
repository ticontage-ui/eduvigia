const browserProtocol = window.location.protocol === "https:" ? "https:" : "http:";
const browserHost = window.location.hostname || "localhost";
const browserPort = window.location.port;
const proxyPorts = new Set(["80", "443", "8088", "18443"]);
const behindProxy = proxyPorts.has(browserPort) || (!browserPort && ["http:", "https:"].includes(browserProtocol));

export const API_URL =
  import.meta.env.VITE_API_URL ||
  (behindProxy
    ? `${window.location.origin}/api`
    : `${browserProtocol}//${browserHost}:8002`);
