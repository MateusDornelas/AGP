import {
  ChatPayload,
  ChatResposta,
  OtimizacaoResposta,
  ReoptimizePayload,
} from "./types";

const TOKEN_KEY = "agp_token";
const USER_KEY = "agp_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): string | null {
  return localStorage.getItem(USER_KEY);
}

export function setSession(token: string, usuario: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, usuario);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function api(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers ?? {});
  const tok = getToken();
  if (tok) headers.set("Authorization", `Bearer ${tok}`);
  const resp = await fetch(path, { ...init, headers });
  if (resp.status === 401) {
    clearSession();
    window.location.reload();
  }
  return resp;
}

export async function login(
  usuario: string,
  senha: string
): Promise<{ token: string; usuario: string }> {
  const resp = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, senha }),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Falha no login");
  }
  return resp.json();
}

export async function optimize(
  file: File,
  modo: string
): Promise<OtimizacaoResposta> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("modo", modo);
  const resp = await api("/api/optimize", { method: "POST", body: fd });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Falha na otimização");
  }
  return resp.json();
}

export async function reoptimize(
  payload: ReoptimizePayload
): Promise<OtimizacaoResposta> {
  const resp = await api("/api/reoptimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Falha na reotimização");
  }
  return resp.json();
}

export async function chat(payload: ChatPayload): Promise<ChatResposta> {
  const resp = await api("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Falha no chat");
  }
  return resp.json();
}
