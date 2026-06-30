/** Static demo — bundled JSON compiled into the Next.js build. */

import type { Alert, AoiFeature, ChangeEvent, DetectionFeature, FeatureCollection, Scene } from "./types";

import bundledAois from "@/demo-data/aois.json";
import bundledDetections from "@/demo-data/detections.json";
import bundledChanges from "@/demo-data/changes.json";
import bundledAlerts from "@/demo-data/alerts.json";
import bundledScenes from "@/demo-data/scenes.json";

const AOI_STORE_KEY = "helios_demo_aois";

const bundledAoiCollection = bundledAois as FeatureCollection<AoiFeature>;

/** Bundled demo is the default for Vercel; set NEXT_PUBLIC_DEMO_MODE=false only for a live API backend. */
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE !== "false";
}

/** Drop corrupted/empty AOI overrides from older broken deploys. */
export function resetDemoStorageIfNeeded(): void {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(AOI_STORE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as { features?: AoiFeature[] };
    if (!parsed.features?.length) {
      localStorage.removeItem(AOI_STORE_KEY);
    }
  } catch {
    localStorage.removeItem(AOI_STORE_KEY);
  }
}

function readAoiOverrides(): AoiFeature[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(AOI_STORE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as { features?: AoiFeature[] };
    return parsed.features ?? [];
  } catch {
    return [];
  }
}

function writeAoiOverrides(features: AoiFeature[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AOI_STORE_KEY, JSON.stringify({ type: "FeatureCollection", features }));
}

function mergeAois(overrides: AoiFeature[]): FeatureCollection<AoiFeature> {
  const base = bundledAoiCollection.features;
  if (!overrides.length) {
    return { type: "FeatureCollection", features: base };
  }
  const byId = new Map(base.map((f) => [f.properties.aoi_id, f]));
  for (const o of overrides) {
    byId.set(o.properties.aoi_id, o);
  }
  return { type: "FeatureCollection", features: [...byId.values()] };
}

export async function demoAois(): Promise<FeatureCollection<AoiFeature>> {
  return mergeAois(readAoiOverrides());
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
  writeAoiOverrides([...readAoiOverrides(), feature]);
  return feature;
}

export async function demoUpdateAoi(
  id: number,
  body: { monitoring_active?: boolean; priority?: string }
): Promise<AoiFeature> {
  const merged = await demoAois();
  const idx = merged.features.findIndex((f) => f.properties.aoi_id === id);
  if (idx < 0) throw new Error("AOI not found");
  const updated = { ...merged.features[idx] };
  if (body.monitoring_active !== undefined) {
    updated.properties = { ...updated.properties, monitoring_active: body.monitoring_active };
  }
  if (body.priority !== undefined) {
    updated.properties = {
      ...updated.properties,
      priority: body.priority as AoiFeature["properties"]["priority"],
    };
  }
  const overrides = readAoiOverrides();
  const oIdx = overrides.findIndex((f) => f.properties.aoi_id === id);
  if (oIdx >= 0) overrides[oIdx] = updated;
  else overrides.push(updated);
  writeAoiOverrides(overrides);
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

/** For debugging — counts baked into the client bundle. */
export function demoDataCounts() {
  return {
    aois: bundledAoiCollection.features.length,
    detections: (bundledDetections as FeatureCollection<DetectionFeature>).features.length,
    changes: (bundledChanges as { events: ChangeEvent[] }).events.length,
    alerts: (bundledAlerts as { alerts: Alert[] }).alerts.length,
  };
}
