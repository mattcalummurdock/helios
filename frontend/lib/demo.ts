/** Static demo mode — bundled JSON compiled into the Next.js build (Vercel-safe). */

import type { Alert, AoiFeature, ChangeEvent, DetectionFeature, FeatureCollection, Scene } from "./types";

import bundledAois from "@/demo-data/aois.json";
import bundledDetections from "@/demo-data/detections.json";
import bundledChanges from "@/demo-data/changes.json";
import bundledAlerts from "@/demo-data/alerts.json";
import bundledScenes from "@/demo-data/scenes.json";

const AOI_STORE_KEY = "helios_demo_aois";

/** Use static demo data when explicitly enabled or when API URL points at localhost (Vercel default). */
export function isDemoMode(): boolean {
  const flag = process.env.NEXT_PUBLIC_DEMO_MODE;
  if (flag === "true") return true;
  if (flag === "false") return false;
  const api = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080").toLowerCase();
  return api.includes("localhost") || api.includes("127.0.0.1");
}

function readAoiStore(): AoiFeature[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AOI_STORE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { features: AoiFeature[] };
    return parsed.features?.length ? parsed.features : null;
  } catch {
    return null;
  }
}

function writeAoiStore(features: AoiFeature[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AOI_STORE_KEY, JSON.stringify({ type: "FeatureCollection", features }));
}

export async function demoAois(): Promise<FeatureCollection<AoiFeature>> {
  const stored = readAoiStore();
  if (stored) {
    return { type: "FeatureCollection", features: stored };
  }
  return bundledAois as FeatureCollection<AoiFeature>;
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

export async function demoDetections(): Promise<FeatureCollection<DetectionFeature>> {
  return bundledDetections as FeatureCollection<DetectionFeature>;
}

export async function demoChanges() {
  return bundledChanges as { events: ChangeEvent[] };
}

export async function demoAlerts() {
  return bundledAlerts as { alerts: Alert[] };
}

export async function demoScenes(aoiId?: number) {
  const { scenes } = bundledScenes as { scenes: Scene[] };
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
