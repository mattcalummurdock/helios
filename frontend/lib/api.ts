import { getApiUrl } from "./api-config";
import {
  demoAlerts,
  demoAois,
  demoChanges,
  demoCreateAoi,
  demoDeactivateAoi,
  demoDetectionImageBlob,
  demoDetections,
  demoScenes,
  demoUpdateAoi,
  isDemoMode,
} from "./demo";
import { demoExportExtension, exportDemoDetections } from "./demo-export";
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

function filterDetections(
  features: DetectionFeature[],
  params: DetectionQuery = {}
): DetectionFeature[] {
  let out = features;
  if (params.aoi_id != null) {
    out = out.filter((f) => f.properties.aoi_id === params.aoi_id);
  }
  if (params.classes?.length) {
    const set = new Set(params.classes);
    out = out.filter((f) => set.has(f.properties.class));
  }
  if (params.confidence_min != null) {
    out = out.filter((f) => f.properties.confidence >= params.confidence_min!);
  }
  if (params.time_start) {
    const start = new Date(params.time_start).getTime();
    out = out.filter((f) => new Date(f.properties.timestamp).getTime() >= start);
  }
  if (params.time_end) {
    const end = new Date(params.time_end).getTime();
    out = out.filter((f) => new Date(f.properties.timestamp).getTime() <= end);
  }
  return out;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, init);
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
  if (isDemoMode()) return demoAois();
  return apiFetch("/aois");
}

export async function createAoi(body: {
  name: string;
  priority: string;
  geometry: { type: "Polygon"; coordinates: number[][][] };
}): Promise<AoiFeature> {
  if (isDemoMode()) return demoCreateAoi(body);
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
  if (isDemoMode()) return demoUpdateAoi(id, body);
  return apiFetch(`/aois/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deactivateAoi(id: number): Promise<{ id: number; monitoring_active: boolean }> {
  if (isDemoMode()) return demoDeactivateAoi(id);
  return apiFetch(`/aois/${id}`, { method: "DELETE" });
}

export async function getDetections(
  params: DetectionQuery = {}
): Promise<FeatureCollection<DetectionFeature>> {
  if (isDemoMode()) {
    const data = await demoDetections();
    return { type: "FeatureCollection", features: filterDetections(data.features, params) };
  }
  return apiFetch(`/detections${queryString(params as Record<string, string | number | undefined | string[]>)}`);
}

export async function getChanges(params: {
  aoi_id?: number;
  time_start?: string;
  time_end?: string;
} = {}): Promise<{ events: ChangeEvent[] }> {
  if (isDemoMode()) {
    const data = await demoChanges();
    let events = data.events;
    if (params.aoi_id != null) events = events.filter((e) => e.aoi_id === params.aoi_id);
    if (params.time_start) {
      const start = new Date(params.time_start).getTime();
      events = events.filter((e) => new Date(e.timestamp).getTime() >= start);
    }
    if (params.time_end) {
      const end = new Date(params.time_end).getTime();
      events = events.filter((e) => new Date(e.timestamp).getTime() <= end);
    }
    return { events };
  }
  return apiFetch(`/changes${queryString(params)}`);
}

export async function getAlerts(params: {
  aoi_id?: number;
  severity?: string;
  acknowledged?: boolean;
} = {}): Promise<{ alerts: Alert[] }> {
  if (isDemoMode()) {
    const data = await demoAlerts();
    let alerts = data.alerts;
    if (params.aoi_id != null) alerts = alerts.filter((a) => a.aoi_id === params.aoi_id);
    if (params.severity) alerts = alerts.filter((a) => a.severity === params.severity);
    if (params.acknowledged != null) alerts = alerts.filter((a) => a.acknowledged === params.acknowledged);
    return { alerts };
  }
  return apiFetch(`/alerts${queryString(params)}`);
}

export async function acknowledgeAlert(
  id: number,
  acknowledgedBy: string
): Promise<{ id: number; acknowledged: boolean; acknowledged_by: string }> {
  if (isDemoMode()) {
    return { id, acknowledged: true, acknowledged_by: acknowledgedBy };
  }
  return apiFetch(`/alerts/${id}/acknowledge`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
  });
}

export async function getScenes(aoiId?: number): Promise<{ scenes: Scene[] }> {
  if (isDemoMode()) return demoScenes(aoiId);
  return apiFetch(`/scenes${queryString({ aoi_id: aoiId })}`);
}

export async function fetchDetectionImageBlob(
  detectionId: number,
  kind: "gradcam" | "crop" = "gradcam"
): Promise<Blob | null> {
  if (isDemoMode()) return demoDetectionImageBlob(detectionId, kind);
  const res = await fetch(`${getApiUrl()}/detections/${detectionId}/${kind}`);
  if (!res.ok) return null;
  return res.blob();
}

/** @deprecated use fetchDetectionImageBlob */
export async function fetchGradCamBlob(detectionId: number): Promise<Blob | null> {
  return fetchDetectionImageBlob(detectionId, "gradcam");
}

export async function exportDetections(params: ExportQuery): Promise<Blob> {
  if (isDemoMode()) return exportDemoDetections(params);
  const res = await fetch(
    `${getApiUrl()}/export${queryString(params as Record<string, string | number | undefined | string[]>)}`
  );
  if (!res.ok) {
    throw new Error(`Export failed: ${res.status}`);
  }
  return res.blob();
}

export { demoExportExtension } from "./demo-export";
