import { isDemoMode } from "./demo";

const TOKEN_KEY = "helios_jwt";
const ANALYST_KEY = "helios_analyst_id";
const DEMO_TOKEN = "demo-static-token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export function getApiUrl(): string {
  return API_URL;
}

export function getWsUrl(): string {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}/ws`;
}

export function getAnalystId(): string {
  if (typeof window === "undefined") return "analyst";
  return localStorage.getItem(ANALYST_KEY) || "analyst";
}

export function setAnalystId(id: string): void {
  localStorage.setItem(ANALYST_KEY, id);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export async function ensureAuth(): Promise<string> {
  if (isDemoMode()) {
    setToken(DEMO_TOKEN);
    return DEMO_TOKEN;
  }

  const existing = getToken();
  if (existing) return existing;

  const analystId = getAnalystId();
  const res = await fetch(`${API_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analyst_id: analystId }),
  });
  if (!res.ok) {
    throw new Error(`Auth failed (${res.status}) at ${API_URL}/auth/token — is the FastAPI backend running?`);
  }
  const data = (await res.json()) as { access_token: string };
  setToken(data.access_token);
  return data.access_token;
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
