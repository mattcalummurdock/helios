/** Static demo mode — serves bundled JSON from /demo/data (no backend). */

import type { AoiFeature } from "./types";

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

const cache = new Map<string, unknown>();
const AOI_STORE_KEY = "helios_demo_aois";

function readAoiStore(): AoiFeature[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AOI_STORE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { features: AoiFeature[] };
    return parsed.features;
  } catch {
    return null;
  }
}

function writeAoiStore(features: AoiFeature[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AOI_STORE_KEY, JSON.stringify({ type: "FeatureCollection", features }));
  cache.set("aois", { type: "FeatureCollection", features });
}

async function loadDemoJson<T>(name: string): Promise<T> {
  const hit = cache.get(name);
  if (hit !== undefined) return hit as T;
  const res = await fetch(`/demo/data/${name}.json`);
  if (!res.ok) throw new Error(`Demo data missing: ${name}.json (run export_demo_static.py)`);
  const data = (await res.json()) as T;
  cache.set(name, data);
  return data;
}

export async function demoAois() {
  const stored = readAoiStore();
  if (stored) {
    return { type: "FeatureCollection" as const, features: stored };
  }
  return loadDemoJson<{ type: string; features: AoiFeature[] }>("aois");
}

export async function demoCreateAoi(body: {
  name: string;
  priority: string;
  geometry: { type: "Polygon"; coordinates: number[][][] };
}): Promise<AoiFeature> {
  const { features } = await demoAois();
  const nextId = features.reduce((m, f) => Math.max(m, f.properties.aoi_id), 0) + 1;
  const feature: AoiFeature = {
    type: "Feature",
    id: nextId,
    geometry: body.geometry,
    properties: {
      aoi_id: nextId,
      name: body.name,
      priority: body.priority as AoiFeature["properties"]["priority"],
      last_pass_at: null,
      monitoring_active: true,
      active_detection_count: 0,
    },
  };
  writeAoiStore([...features, feature]);
  return feature;
}

export async function demoUpdateAoi(
  id: number,
  body: { monitoring_active?: boolean; priority?: string }
): Promise<AoiFeature> {
  const { features } = await demoAois();
  const idx = features.findIndex((f) => f.properties.aoi_id === id);
  if (idx < 0) throw new Error("AOI not found");
  const updated = { ...features[idx] };
  if (body.monitoring_active !== undefined) {
    updated.properties = { ...updated.properties, monitoring_active: body.monitoring_active };
  }
  if (body.priority !== undefined) {
    updated.properties = {
      ...updated.properties,
      priority: body.priority as AoiFeature["properties"]["priority"],
    };
  }
  const next = [...features];
  next[idx] = updated;
  writeAoiStore(next);
  return updated;
}

export async function demoDeactivateAoi(id: number): Promise<{ id: number; monitoring_active: boolean }> {
  await demoUpdateAoi(id, { monitoring_active: false });
  return { id, monitoring_active: false };
}

export async function demoDetections() {
  return loadDemoJson<{ type: string; features: import("./types").DetectionFeature[] }>(
    "detections"
  );
}

export async function demoChanges() {
  return loadDemoJson<{ events: import("./types").ChangeEvent[] }>("changes");
}

export async function demoAlerts() {
  return loadDemoJson<{ alerts: import("./types").Alert[] }>("alerts");
}

export async function demoScenes(aoiId?: number) {
  const { scenes } = await loadDemoJson<{ scenes: import("./types").Scene[] }>("scenes");
  if (aoiId == null) return { scenes };
  return { scenes: scenes.filter((s) => s.aoi_id === aoiId) };
}

export async function demoDetectionImageBlob(
  detectionId: number,
  kind: "gradcam" | "crop"
): Promise<Blob | null> {
  const res = await fetch(`/demo/images/detections/${detectionId}/${kind}.png`);
  if (!res.ok) return null;
  return res.blob();
}
