import {
  ensureAuth,
  authHeaders,
  getApiUrl,
} from "./auth";
import type {
  Alert,
  AoiFeature,
  ChangeEvent,
  DetectionFeature,
  DetectionQuery,
  ExportQuery,
  FeatureCollection,
  Scene,
} from "./types";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  await ensureAuth();
  const res = await fetch(`${getApiUrl()}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `API error ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json") || ct.includes("geo+json")) {
    return res.json() as Promise<T>;
  }
  return res as unknown as T;
}

function queryString(params: Record<string, string | number | boolean | undefined | string[]>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      v.forEach((item) => sp.append(k, item));
    } else {
      sp.set(k, String(v));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export async function getAois(): Promise<FeatureCollection<AoiFeature>> {
  return apiFetch("/aois");
}

export async function createAoi(body: {
  name: string;
  priority: string;
  geometry: { type: "Polygon"; coordinates: number[][][] };
}): Promise<AoiFeature> {
  return apiFetch("/aois", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateAoi(
  id: number,
  body: { monitoring_active?: boolean; priority?: string }
): Promise<AoiFeature> {
  return apiFetch(`/aois/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deactivateAoi(id: number): Promise<{ id: number; monitoring_active: boolean }> {
  return apiFetch(`/aois/${id}`, { method: "DELETE" });
}

export async function getDetections(
  params: DetectionQuery = {}
): Promise<FeatureCollection<DetectionFeature>> {
  return apiFetch(`/detections${queryString(params as Record<string, string | number | undefined | string[]>)}`);
}

export async function getChanges(params: {
  aoi_id?: number;
  time_start?: string;
  time_end?: string;
} = {}): Promise<{ events: ChangeEvent[] }> {
  return apiFetch(`/changes${queryString(params)}`);
}

export async function getAlerts(params: {
  aoi_id?: number;
  severity?: string;
  acknowledged?: boolean;
} = {}): Promise<{ alerts: Alert[] }> {
  return apiFetch(`/alerts${queryString(params)}`);
}

export async function acknowledgeAlert(
  id: number,
  acknowledgedBy: string
): Promise<{ id: number; acknowledged: boolean; acknowledged_by: string }> {
  return apiFetch(`/alerts/${id}/acknowledge`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
  });
}

export async function getScenes(aoiId?: number): Promise<{ scenes: Scene[] }> {
  return apiFetch(`/scenes${queryString({ aoi_id: aoiId })}`);
}

export async function fetchDetectionImageBlob(
  detectionId: number,
  kind: "gradcam" | "crop" = "gradcam"
): Promise<Blob | null> {
  await ensureAuth();
  const res = await fetch(`${getApiUrl()}/detections/${detectionId}/${kind}`, {
    headers: authHeaders(),
  });
  if (!res.ok) return null;
  return res.blob();
}

/** @deprecated use fetchDetectionImageBlob */
export async function fetchGradCamBlob(detectionId: number): Promise<Blob | null> {
  return fetchDetectionImageBlob(detectionId, "gradcam");
}

export async function exportDetections(params: ExportQuery): Promise<Blob> {
  await ensureAuth();
  const res = await fetch(
    `${getApiUrl()}/export${queryString(params as Record<string, string | number | undefined | string[]>)}`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    throw new Error(`Export failed: ${res.status}`);
  }
  return res.blob();
}

export async function getHealth(): Promise<{
  status: string;
  db?: string;
  phase?: number;
  ws_clients?: number;
}> {
  const res = await fetch(`${getApiUrl()}/health`);
  return res.json();
}
