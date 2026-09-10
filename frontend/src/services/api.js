import { API_URL } from "../config/runtime";

const TOKEN_KEY = "eduvigia_token";
const USER_KEY = "eduvigia_user";

export async function api(path, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error("Não foi possível conectar ao servidor EduVigIA.");
  }

  if (response.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new Event("eduvigia-auth-expired"));
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Falha na operação (HTTP ${response.status})`);
  }

  return response.status === 204 ? null : response.json();
}
