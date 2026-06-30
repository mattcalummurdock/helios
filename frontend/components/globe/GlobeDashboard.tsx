"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadCesium, type CesiumNamespace } from "@/lib/cesium-loader";
import { getAois, getChanges, getDetections, getScenes } from "@/lib/api";
import { detectionModelLabel } from "@/lib/detection-display";
import { isDemoMode, demoDataCounts } from "@/lib/demo";
import { HeliosWebSocket } from "@/lib/ws";
import { iconForClass, scaleForConfidence, CHANGE_COLORS, aoiStyle } from "@/lib/icons";
import type {
  Alert,
  AoiFeature,
  ChangeEvent,
  DetectionFeature,
  Scene,
  WsEvent,
} from "@/lib/types";
import { DetectionPanel } from "@/components/detection/DetectionPanel";
import { AlertPanel } from "@/components/alerts/AlertPanel";
import { TimelineScrubber } from "@/components/timeline/TimelineScrubber";
import { ExportModal } from "@/components/export/ExportModal";

const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN || "";

function aoiBbox(coords: number[][][]) {
  const ring = coords[0];
  let west = Infinity,
    east = -Infinity,
    south = Infinity,
    north = -Infinity;
  ring.forEach(([lon, lat]) => {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  });
  return { west, south, east, north };
}

function aoiCentroid(coords: number[][][]) {
  const ring = coords[0];
  const n = ring.length - 1;
  let lon = 0,
    lat = 0;
  for (let i = 0; i < n; i++) {
    lon += ring[i][0];
    lat += ring[i][1];
  }
  return { lon: lon / n, lat: lat / n };
}

function changeBounds(events: ChangeEvent[]) {
  let west = Infinity,
    east = -Infinity,
    south = Infinity,
    north = -Infinity;
  events.forEach((ch) => {
    [ch.t1, ch.t2].forEach((pt) => {
      if (!pt) return;
      west = Math.min(west, pt.lon);
      east = Math.max(east, pt.lon);
      south = Math.min(south, pt.lat);
      north = Math.max(north, pt.lat);
    });
  });
  if (!Number.isFinite(west)) return null;
  return { west, east, south, north };
}

function flyToChangeEvents(
  viewer: any,
  Cesium: CesiumNamespace,
  events: ChangeEvent[]
) {
  const bounds = changeBounds(events);
  if (!bounds) return;
  const centerLon = (bounds.west + bounds.east) / 2;
  const centerLat = (bounds.south + bounds.north) / 2;
  const spanDeg = Math.max(bounds.east - bounds.west, bounds.north - bounds.south, 0.01);
  // Close enough to see movement arrows (km-scale), not continent view
  const altitudeM = Math.min(Math.max(spanDeg * 111000 * 4, 12000), 120000);
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(centerLon, centerLat, altitudeM),
    duration: 1.2,
  });
}

function coverageColor(Cesium: CesiumNamespace, hoursAgo: number) {
  if (hoursAgo < 6) return Cesium.Color.fromCssColorString("#98c379").withAlpha(0.55);
  if (hoursAgo < 48) return Cesium.Color.fromCssColorString("#e5c07b").withAlpha(0.55);
  return Cesium.Color.fromCssColorString("#e06c75").withAlpha(0.55);
}

function coverageOutlineColor(Cesium: CesiumNamespace, hoursAgo: number) {
  if (hoursAgo < 6) return Cesium.Color.fromCssColorString("#b8e986");
  if (hoursAgo < 48) return Cesium.Color.fromCssColorString("#ffd866");
  return Cesium.Color.fromCssColorString("#ff6b6b");
}

export default function GlobeDashboard() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const cesiumRef = useRef<CesiumNamespace | null>(null);
  const entityMapRef = useRef<Map<string, DetectionFeature | ChangeEvent>>(new Map());
  const handlerRef = useRef<any>(null);

  const [cesiumReady, setCesiumReady] = useState(false);
  const [aois, setAois] = useState<AoiFeature[]>([]);
  const [detections, setDetections] = useState<DetectionFeature[]>([]);
  const [allDetections, setAllDetections] = useState<DetectionFeature[]>([]);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [scenesByAoi, setScenesByAoi] = useState<Map<number, Scene>>(new Map());
  const [selectedDetection, setSelectedDetection] = useState<DetectionFeature | null>(null);
  const [selectedChange, setSelectedChange] = useState<ChangeEvent | null>(null);
  const [processingAois, setProcessingAois] = useState<Set<number>>(new Set());
  const [pulseOn, setPulseOn] = useState(true);
  const [isLive, setIsLive] = useState(() => !isDemoMode());
  const [timeEnd, setTimeEnd] = useState<Date | null>(null);
  const [showDetections, setShowDetections] = useState(true);
  const [showAois, setShowAois] = useState(true);
  const [showChanges, setShowChanges] = useState(true);
  const [showCoverage, setShowCoverage] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [alertCount, setAlertCount] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [newAlerts, setNewAlerts] = useState<Alert[]>([]);
  const [flyTarget, setFlyTarget] = useState<{ lon: number; lat: number } | null>(null);
  const initialFlyDone = useRef(false);
  const dismissAlertsRef = useRef<() => void>(() => {});
  dismissAlertsRef.current = () => setAlertsOpen(false);

  const pulseAlpha = pulseOn ? 0.9 : 0.3;

  useEffect(() => {
    const id = setInterval(() => setPulseOn((p) => !p), 500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let destroyed = false;
    loadCesium()
      .then((Cesium) => {
        if (destroyed || !containerRef.current) return;
        cesiumRef.current = Cesium;
        const viewer = new Cesium.Viewer(containerRef.current, {
          timeline: false,
          animation: false,
          baseLayerPicker: false,
          geocoder: false,
          homeButton: true,
          infoBox: false,
          navigationHelpButton: false,
          sceneModePicker: false,
          terrain: Cesium.Terrain.fromWorldTerrain(),
        });
        viewerRef.current = viewer;

        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((movement: { position: { x: number; y: number } }) => {
          const picked = viewer.scene.pick(movement.position);
          if (!Cesium.defined(picked) || !picked.id) {
            viewer.selectedEntity = undefined;
            setSelectedDetection(null);
            setSelectedChange(null);
            return;
          }
          const id = picked.id.id as string;
          let data = entityMapRef.current.get(id);
          if (!data && id.startsWith("ch-")) {
            const baseId = id.replace(/-(t1|t2)$/, "");
            data = entityMapRef.current.get(baseId);
          }
          if (!data) {
            viewer.selectedEntity = undefined;
            return;
          }
          dismissAlertsRef.current();
          viewer.selectedEntity = picked.id;
          if ("properties" in data) {
            setSelectedDetection(data as DetectionFeature);
            setSelectedChange(null);
          } else {
            setSelectedChange(data as ChangeEvent);
            setSelectedDetection(null);
          }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        handlerRef.current = handler;

        setCesiumReady(true);
      })
      .catch(console.error);

    return () => {
      destroyed = true;
      handlerRef.current?.destroy();
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
  }, []);

  const loadData = useCallback(async () => {
    setLoadError(null);
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    try {
      const [aoiData, changeData, detAll] = await Promise.all([
        getAois(),
        getChanges(),
        getDetections({ time_start: thirtyDaysAgo.toISOString() }),
      ]);

      setAois(aoiData.features);
      setChanges(changeData.events);
      setAllDetections(detAll.features);
      setDetections(detAll.features);

      if (
        isDemoMode() &&
        aoiData.features.length === 0 &&
        demoDataCounts().aois > 0
      ) {
        setLoadError("Demo data failed to load — redeploy with frontend/demo-data/ committed.");
        return;
      }

      if (aoiData.features.length > 0 && !initialFlyDone.current) {
        const c = aoiCentroid(aoiData.features[0].geometry.coordinates);
        setFlyTarget(c);
        initialFlyDone.current = true;
      }

      const sceneMap = new Map<number, Scene>();
      await Promise.all(
        aoiData.features.map(async (a) => {
          const { scenes } = await getScenes(a.properties.aoi_id);
          if (scenes[0]) sceneMap.set(a.properties.aoi_id, scenes[0]);
        })
      );
      setScenesByAoi(sceneMap);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load surveillance data";
      setLoadError(msg);
      console.error("loadData failed:", e);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const refreshDetections = useCallback(async (end?: Date | null) => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const params: { time_start: string; time_end?: string } = {
      time_start: thirtyDaysAgo.toISOString(),
    };
    if (end) params.time_end = end.toISOString();
    const data = await getDetections(params);
    setDetections(data.features);
    if (!end) setAllDetections(data.features);
  }, []);

  useEffect(() => {
    if (!isLive && timeEnd) refreshDetections(timeEnd).catch(console.error);
  }, [isLive, timeEnd, refreshDetections]);

  useEffect(() => {
    if (isDemoMode()) return;

    const ws = new HeliosWebSocket({
      onEvent: (event: WsEvent) => {
        if (event.type === "detection_created" && isLive) {
          const f = event.payload.feature;
          setDetections((prev) => {
            if (prev.some((d) => d.properties.detection_id === f.properties.detection_id)) return prev;
            return [f, ...prev];
          });
          setAllDetections((prev) => {
            if (prev.some((d) => d.properties.detection_id === f.properties.detection_id)) return prev;
            return [f, ...prev];
          });
        } else if (event.type === "change_detected") {
          setChanges((prev) => {
            if (prev.some((c) => c.id === event.payload.id)) return prev;
            return [event.payload, ...prev];
          });
        } else if (event.type === "alert_fired") {
          const p = event.payload;
          setNewAlerts((prev) => [
            {
              id: p.id,
              aoi_id: p.aoi_id,
              aoi_name: p.aoi_name,
              change_event_id: null,
              alert_type: p.alert_type,
              severity: p.severity,
              lat: p.lat,
              lon: p.lon,
              description: p.description,
              acknowledged: false,
              acknowledged_by: null,
              timestamp: p.timestamp,
            },
            ...prev,
          ]);
        } else if (event.type === "scene_processing") {
          setProcessingAois((prev) => new Set(prev).add(event.payload.aoi_id));
        } else if (event.type === "scene_processing_complete") {
          setProcessingAois((prev) => {
            const next = new Set(prev);
            next.delete(event.payload.aoi_id);
            return next;
          });
          getScenes(event.payload.aoi_id).then(({ scenes }) => {
            if (scenes[0]) setScenesByAoi((m) => new Map(m).set(event.payload.aoi_id, scenes[0]));
          });
          getAois().then((d) => setAois(d.features));
        }
      },
      onReconnect: () => {
        if (isLive) refreshDetections().catch(console.error);
      },
    });
    ws.connect().catch(console.error);
    return () => ws.disconnect();
  }, [isLive, refreshDetections]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !cesiumReady) return;

    viewer.entities.removeAll();
    entityMapRef.current.clear();

    if (showAois) {
      aois.forEach((aoi) => {
        const props = aoi.properties;
        const isProcessing = processingAois.has(props.aoi_id);
        const scene = scenesByAoi.get(props.aoi_id);
        const tooltip = [
          props.name,
          `Priority: ${props.priority}`,
          props.last_pass_at
            ? `Last pass: ${new Date(props.last_pass_at).toLocaleString()}`
            : "No passes yet",
          props.last_satellite_source
            ? `Satellite: ${props.last_satellite_source}`
            : scene
              ? `Satellite: ${scene.satellite_source}`
              : "",
          `Active detections: ${props.active_detection_count ?? 0}`,
        ]
          .filter(Boolean)
          .join("\n");

        const positions = aoi.geometry.coordinates[0].map(([lon, lat]) =>
          Cesium.Cartesian3.fromDegrees(lon, lat)
        );
        const style = aoiStyle(props.priority);
        const fill = Cesium.Color.fromCssColorString(style.fill).withAlpha(0.42);
        const stroke = Cesium.Color.fromCssColorString(style.stroke);
        const centroid = aoiCentroid(aoi.geometry.coordinates);

        viewer.entities.add({
          id: `aoi-${props.aoi_id}`,
          name: tooltip,
          polygon: {
            hierarchy: positions,
            material: fill,
            outline: false,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        });

        const closed = [...positions, positions[0]];
        viewer.entities.add({
          id: `aoi-border-${props.aoi_id}`,
          polyline: {
            positions: closed,
            width: isProcessing ? 5 : 4,
            clampToGround: true,
            material: stroke,
            depthFailMaterial: stroke.withAlpha(0.85),
          },
        });

        viewer.entities.add({
          id: `aoi-label-${props.aoi_id}`,
          position: Cesium.Cartesian3.fromDegrees(centroid.lon, centroid.lat, 0),
          label: {
            text: props.name,
            font: "bold 13px sans-serif",
            fillColor: Cesium.Color.fromCssColorString(style.label),
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 3,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: Cesium.VerticalOrigin.CENTER,
            horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            scaleByDistance: new Cesium.NearFarScalar(5000, 1.2, 8_000_000, 0.55),
            pixelOffsetScaleByDistance: new Cesium.NearFarScalar(5000, 1, 8_000_000, 0.4),
          },
        });
      });
    }

    if (showCoverage) {
      aois.forEach((aoi) => {
        const scene = scenesByAoi.get(aoi.properties.aoi_id);
        if (!scene) return;
        const hoursAgo =
          (Date.now() - new Date(scene.acquisition_timestamp).getTime()) / 3600000;
        const bbox = aoiBbox(aoi.geometry.coordinates);
        const tooltip = [
          `Last pass: ${new Date(scene.acquisition_timestamp).toLocaleString()}`,
          `Satellite: ${scene.satellite_source}`,
          scene.cloud_cover_pct != null
            ? `Cloud cover: ${(scene.cloud_cover_pct * 100).toFixed(0)}%`
            : "",
        ]
          .filter(Boolean)
          .join("\n");

        viewer.entities.add({
          id: `coverage-${aoi.properties.aoi_id}`,
          name: tooltip,
          rectangle: {
            coordinates: Cesium.Rectangle.fromDegrees(
              bbox.west,
              bbox.south,
              bbox.east,
              bbox.north
            ),
            material: coverageColor(Cesium, hoursAgo),
            outline: true,
            outlineColor: coverageOutlineColor(Cesium, hoursAgo),
            outlineWidth: 3,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        });
      });
    }

    if (showChanges) {
      changes.forEach((ch) => {
        const color = CHANGE_COLORS[ch.event_type] || "#e5c07b";
        const cesiumColor = Cesium.Color.fromCssColorString(color);
        const id = `ch-${ch.id}`;

        if (ch.t1 && ch.t2) {
          entityMapRef.current.set(id, ch);
          viewer.entities.add({
            id,
            name: `${ch.event_type} — ${ch.t2.class}`,
            polyline: {
              positions: Cesium.Cartesian3.fromDegreesArray([
                ch.t1.lon,
                ch.t1.lat,
                ch.t2.lon,
                ch.t2.lat,
              ]),
              width: 14,
              clampToGround: true,
              arcType: Cesium.ArcType.GEODESIC,
              material: new Cesium.PolylineArrowMaterialProperty(cesiumColor),
              depthFailMaterial: new Cesium.PolylineArrowMaterialProperty(cesiumColor),
            },
          });
          ["t1", "t2"].forEach((end, idx) => {
            const pt = end === "t1" ? ch.t1! : ch.t2!;
            const endId = `${id}-${end}`;
            entityMapRef.current.set(endId, ch);
            viewer.entities.add({
              id: endId,
              position: Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, 0),
              point: {
                pixelSize: idx === 0 ? 10 : 14,
                color: cesiumColor,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
              },
            });
          });
          return;
        }

        const pt = ch.t2 ?? ch.t1;
        if (!pt) return;
        entityMapRef.current.set(id, ch);
        viewer.entities.add({
          id,
          position: Cesium.Cartesian3.fromDegrees(pt.lon, pt.lat, 0),
          name: `${ch.event_type} — ${pt.class}`,
          point: {
            pixelSize: 16,
            color: cesiumColor,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        });
      });
    }

    if (showDetections) {
      detections.forEach((det) => {
        const p = det.properties;
        const id = `det-${p.detection_id}`;
        entityMapRef.current.set(id, det);
        const label = detectionModelLabel(p.class, p.subclass) ?? p.class;
        viewer.entities.add({
          id,
          position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, 0),
          name: `${label} (${(p.confidence * 100).toFixed(0)}%)`,
          billboard: {
            image: iconForClass(p.class),
            scale: scaleForConfidence(p.confidence),
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        });
      });
    }
  }, [
    cesiumReady,
    aois,
    detections,
    changes,
    scenesByAoi,
    processingAois,
    showAois,
    showDetections,
    showChanges,
    showCoverage,
  ]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !cesiumReady) return;
    if (selectedDetection) {
      const ent = viewer.entities.getById(
        `det-${selectedDetection.properties.detection_id}`
      );
      viewer.selectedEntity = ent ?? undefined;
    } else if (selectedChange) {
      const ent = viewer.entities.getById(`ch-${selectedChange.id}`);
      viewer.selectedEntity = ent ?? undefined;
    } else {
      viewer.selectedEntity = undefined;
    }
  }, [cesiumReady, selectedDetection, selectedChange, detections, changes, showDetections, showChanges]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium) return;
    processingAois.forEach((aoiId) => {
      const border = viewer.entities.getById(`aoi-border-${aoiId}`);
      if (border?.polyline) {
        border.polyline.width = pulseAlpha > 0.6 ? 6 : 4;
      }
    });
  }, [pulseAlpha, processingAois]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !flyTarget) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(flyTarget.lon, flyTarget.lat, 250000),
      duration: 1.5,
    });
  }, [flyTarget, cesiumReady]);

  const handleGoLive = () => {
    setIsLive(true);
    setTimeEnd(null);
    refreshDetections().catch(console.error);
  };

  const handleToggleVectors = () => {
    setShowChanges((prev) => {
      const next = !prev;
      if (next && changes.length > 0 && viewerRef.current && cesiumRef.current) {
        flyToChangeEvents(viewerRef.current, cesiumRef.current, changes);
      }
      return next;
    });
  };

  const handleToggleAlerts = useCallback(() => {
    setAlertsOpen((open) => {
      if (!open) {
        setSelectedDetection(null);
        setSelectedChange(null);
        const viewer = viewerRef.current;
        if (viewer) viewer.selectedEntity = undefined;
      }
      return !open;
    });
  }, []);
  const handleFlyTo = useCallback((lat: number, lon: number) => {
    const viewer = viewerRef.current;
    const Cesium = cesiumRef.current;
    setAlertsOpen(false);
    setSelectedDetection(null);
    setSelectedChange(null);
    if (viewer && Cesium) {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(lon, lat, 18000),
        duration: 1.2,
      });
      return;
    }
    setFlyTarget({ lon, lat });
  }, []);

  if (!ION_TOKEN) {
    return (
      <div className="auth-error">
        <h2>Cesium Ion token required</h2>
        <p>
          Set <code>CESIUM_ION_TOKEN</code> or <code>NEXT_PUBLIC_CESIUM_ION_TOKEN</code> in{" "}
          <code>frontend/.env</code> and rebuild.
        </p>
      </div>
    );
  }

  return (
    <div className="globe-container">
      {loadError && (
        <div
          className="auth-error"
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 20,
            maxWidth: "90%",
            padding: "0.75rem 1rem",
          }}
        >
          <strong>Data load error:</strong> {loadError}
        </div>
      )}
      <div className="globe-toolbar-row">
        <div className="globe-toolbar">
          <button
            className={`toolbar-btn ${showDetections ? "active" : ""}`}
            onClick={() => setShowDetections((v) => !v)}
          >
            Detections
          </button>
          <button
            className={`toolbar-btn ${showAois ? "active" : ""}`}
            onClick={() => setShowAois((v) => !v)}
          >
            AOIs
          </button>
          <button
            className={`toolbar-btn ${showChanges ? "active" : ""}`}
            onClick={handleToggleVectors}
            title={
              changes.length === 0
                ? "No change vectors yet (needs T1/T2 pass comparison)"
                : `${changes.length} movement vector(s) — click to fly to them`
            }
          >
            Vectors{changes.length > 0 ? ` (${changes.length})` : ""}
          </button>
          <button
            className={`toolbar-btn ${showCoverage ? "active" : ""}`}
            onClick={() => setShowCoverage((v) => !v)}
          >
            Coverage
          </button>
          <button className="toolbar-btn" onClick={() => setExportOpen(true)}>
            Export
          </button>
        </div>
        <div className="globe-toolbar-right">
          <button
            className={`toolbar-btn toolbar-btn-alert ${alertsOpen ? "active" : ""}`}
            onClick={handleToggleAlerts}
            aria-label="Alerts"
          >
            Alerts
            {alertCount > 0 && <span className="alert-badge">{alertCount}</span>}
          </button>
        </div>
      </div>

      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {!cesiumReady && (
        <div className="auth-loading" style={{ position: "absolute", inset: 0 }}>
          Loading 3D globe…
        </div>
      )}

      {!alertsOpen && (
        <DetectionPanel detection={selectedDetection} onClose={() => setSelectedDetection(null)} />
      )}

      {!alertsOpen && selectedChange && (
        <div className="panel change-detail-panel">
          <button className="panel-close" onClick={() => setSelectedChange(null)}>
            ×
          </button>
          <h3>Change Event #{selectedChange.id}</h3>
          <div className="row">
            <span>Type</span>
            <span>{selectedChange.event_type}</span>
          </div>
          <div className="row">
            <span>Class</span>
            <span>{selectedChange.t2?.class || selectedChange.t1?.class || "—"}</span>
          </div>
          {selectedChange.distance_moved_m != null && (
            <div className="row">
              <span>Distance</span>
              <span>{selectedChange.distance_moved_m.toFixed(0)} m</span>
            </div>
          )}
          {selectedChange.speed_kmh != null && (
            <div className="row">
              <span>Speed</span>
              <span>{selectedChange.speed_kmh.toFixed(1)} km/h</span>
            </div>
          )}
          {selectedChange.bearing_degrees != null && (
            <div className="row">
              <span>Bearing</span>
              <span>{selectedChange.bearing_degrees.toFixed(1)}°</span>
            </div>
          )}
          <div className="row">
            <span>Time</span>
            <span>{new Date(selectedChange.timestamp).toLocaleString()}</span>
          </div>
        </div>
      )}

      <AlertPanel
        open={alertsOpen}
        onClose={() => setAlertsOpen(false)}
        aois={aois}
        onFlyTo={handleFlyTo}
        onCountChange={setAlertCount}
        externalAlerts={newAlerts}
      />

      <TimelineScrubber
        detections={allDetections}
        isLive={isLive}
        timeEnd={timeEnd}
        onTimeEndChange={(d) => {
          setIsLive(false);
          setTimeEnd(d);
        }}
        onGoLive={handleGoLive}
      />

      <ExportModal open={exportOpen} onClose={() => setExportOpen(false)} aois={aois} />
    </div>
  );
}
