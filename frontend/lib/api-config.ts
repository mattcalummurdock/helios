const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export function getApiUrl(): string {
  return API_URL;
}

export function getWsUrl(): string {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}/ws`;
}
