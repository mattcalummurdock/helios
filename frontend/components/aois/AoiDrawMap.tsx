"use client";

import { aoiStyle } from "@/lib/icons";
import { AoiDraftPopup } from "@/components/aois/AoiDraftPopup";
import type { AoiFeature } from "@/lib/types";
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import "leaflet-draw";

type DraftFormProps = {
  name: string;
  priority: "high" | "medium" | "low";
  saving: boolean;
  error: string | null;
  onNameChange: (value: string) => void;
  onPriorityChange: (value: "high" | "medium" | "low") => void;
  onSave: () => void;
  onCancel: () => void;
};

type Props = {
  onPolygonDrawn: (coords: number[][][] | null) => void;
  onDrawStart?: () => void;
  draftPolygon?: number[][][] | null;
  draftForm?: DraftFormProps | null;
  aois?: AoiFeature[];
  focusedAoiId?: number | null;
  center?: [number, number];
};

const DRAFT_STYLE: L.PathOptions = {
  color: "#7fdbca",
  fillColor: "#7fdbca",
  fillOpacity: 0.4,
  weight: 4,
};

function aoiCentroid(coords: number[][][]): [number, number] {
  const ring = coords[0];
  const n = ring.length - 1;
  let lon = 0;
  let lat = 0;
  for (let i = 0; i < n; i++) {
    lon += ring[i][0];
    lat += ring[i][1];
  }
  return [lat / n, lon / n];
}

function coordsToLatLngs(coords: number[][][]): L.LatLng[] {
  return coords[0].map(([lon, lat]) => L.latLng(lat, lon));
}

function polygonStyle(aoi: AoiFeature, focused: boolean): L.PathOptions {
  const style = aoiStyle(aoi.properties.priority);
  const active = aoi.properties.monitoring_active;
  return {
    color: active ? style.stroke : "#5c7a8a",
    fillColor: active ? style.fill : "#3a4550",
    fillOpacity: active ? 0.38 : 0.1,
    weight: focused ? 4 : active ? 3 : 2,
    dashArray: active ? undefined : "10 8",
    opacity: active ? 1 : 0.55,
  };
}

function aoiPolygonBounds(aoi: AoiFeature): L.LatLngBounds | null {
  const bounds = L.geoJSON(aoi as GeoJSON.Feature).getBounds();
  return bounds.isValid() ? bounds : null;
}

function draftBounds(coords: number[][][]): L.LatLngBounds | null {
  const bounds = L.polygon(coordsToLatLngs(coords)).getBounds();
  return bounds.isValid() ? bounds : null;
}

function allAoisBounds(aois: AoiFeature[]): L.LatLngBounds | null {
  const bounds = L.latLngBounds([]);
  let valid = false;
  for (const aoi of aois) {
    const b = aoiPolygonBounds(aoi);
    if (b) {
      bounds.extend(b);
      valid = true;
    }
  }
  return valid ? bounds : null;
}

function safeFitBounds(
  map: L.Map,
  bounds: L.LatLngBounds,
  options?: L.FitBoundsOptions
) {
  const container = map.getContainer();
  if (!container?.offsetWidth || !container?.offsetHeight) return;
  if (!bounds.isValid()) return;
  try {
    map.stop();
    map.invalidateSize();
    map.fitBounds(bounds, {
      padding: [48, 48],
      animate: false,
      ...options,
    });
  } catch {
    // Map may be mid-teardown during route transitions.
  }
}

export function AoiDrawMap({
  onPolygonDrawn,
  onDrawStart,
  draftPolygon = null,
  draftForm = null,
  aois = [],
  focusedAoiId = null,
  center = [49.0, 32.0],
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);
  const aoiLayersRef = useRef<L.FeatureGroup | null>(null);
  const onPolygonDrawnRef = useRef(onPolygonDrawn);
  const onDrawStartRef = useRef(onDrawStart);
  const initialFitDoneRef = useRef(false);
  const isDrawingRef = useRef(false);
  const cameraFrameRef = useRef<number | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [popupPos, setPopupPos] = useState<{ x: number; y: number } | null>(null);
  onPolygonDrawnRef.current = onPolygonDrawn;
  onDrawStartRef.current = onDrawStart;

  const cancelCameraFrame = () => {
    if (cameraFrameRef.current != null) {
      cancelAnimationFrame(cameraFrameRef.current);
      cameraFrameRef.current = null;
    }
  };

  const scheduleCamera = (fn: () => void) => {
    cancelCameraFrame();
    cameraFrameRef.current = requestAnimationFrame(() => {
      cameraFrameRef.current = requestAnimationFrame(() => {
        cameraFrameRef.current = null;
        if (isDrawingRef.current) return;
        fn();
      });
    });
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let disposed = false;
    const map = L.map(containerRef.current).setView(center, 6);
    mapRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    const aoiLayers = new L.FeatureGroup();
    map.addLayer(aoiLayers);
    aoiLayersRef.current = aoiLayers;

    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnItemsRef.current = drawnItems;

    const drawControl = new L.Control.Draw({
      draw: {
        marker: false,
        circle: false,
        circlemarker: false,
        polyline: false,
        rectangle: false,
        polygon: {
          allowIntersection: false,
          showArea: false,
        },
      },
      edit: {
        featureGroup: drawnItems,
      },
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.DRAWSTART, () => {
      isDrawingRef.current = true;
      cancelCameraFrame();
      onDrawStartRef.current?.();
    });
    map.on(L.Draw.Event.DRAWSTOP, () => {
      isDrawingRef.current = false;
    });

    map.on(L.Draw.Event.CREATED, (e: L.LeafletEvent) => {
      isDrawingRef.current = false;
      const event = e as L.DrawEvents.Created;
      const geo = event.layer.toGeoJSON();
      if (geo.geometry.type === "Polygon") {
        const coords = geo.geometry.coordinates as number[][][];
        onPolygonDrawnRef.current(coords);
      }
    });

    map.on(L.Draw.Event.EDITED, () => {
      drawnItems.eachLayer((layer) => {
        const geo = (layer as L.Polygon).toGeoJSON();
        if (geo.geometry.type === "Polygon") {
          onPolygonDrawnRef.current(geo.geometry.coordinates as number[][][]);
        }
      });
    });

    map.on(L.Draw.Event.DELETED, () => {
      onPolygonDrawnRef.current(null);
    });

    map.whenReady(() => {
      if (disposed) return;
      map.invalidateSize();
      setMapReady(true);
    });

    return () => {
      disposed = true;
      cancelCameraFrame();
      setMapReady(false);
      initialFitDoneRef.current = false;
      try {
        map.stop();
        map.remove();
      } catch {
        // ignore
      }
      mapRef.current = null;
      aoiLayersRef.current = null;
      drawnItemsRef.current = null;
    };
  }, [center]);

  useEffect(() => {
    const map = mapRef.current;
    const aoiLayers = aoiLayersRef.current;
    if (!mapReady || !map || !aoiLayers || isDrawingRef.current) return;

    aoiLayers.clearLayers();

    aois.forEach((aoi) => {
      const focused = aoi.properties.aoi_id === focusedAoiId;
      const layer = L.geoJSON(aoi as GeoJSON.Feature, {
        style: () => polygonStyle(aoi, focused),
      });
      layer.bindTooltip(
        `${aoi.properties.name} (${aoi.properties.monitoring_active ? "active" : "inactive"})`,
        { sticky: true }
      );
      aoiLayers.addLayer(layer);

      const [lat, lon] = aoiCentroid(aoi.geometry.coordinates);
      const style = aoiStyle(aoi.properties.priority);
      const label = L.marker([lat, lon], {
        icon: L.divIcon({
          className: "aoi-map-label",
          html: `<span class="aoi-map-label-text ${
            aoi.properties.monitoring_active ? "" : "inactive"
          }" style="border-color:${style.stroke}">${aoi.properties.name}</span>`,
          iconSize: [0, 0],
        }),
        interactive: false,
      });
      aoiLayers.addLayer(label);
    });
  }, [mapReady, aois, focusedAoiId]);

  useEffect(() => {
    const drawnItems = drawnItemsRef.current;
    if (!mapReady || !drawnItems || isDrawingRef.current) return;

    drawnItems.clearLayers();
    if (!draftPolygon) return;

    const layer = L.polygon(coordsToLatLngs(draftPolygon), DRAFT_STYLE);
    drawnItems.addLayer(layer);
  }, [mapReady, draftPolygon]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || !draftPolygon || !draftForm) {
      setPopupPos(null);
      return;
    }

    const updatePos = () => {
      const [lat, lon] = aoiCentroid(draftPolygon);
      const point = map.latLngToContainerPoint(L.latLng(lat, lon));
      setPopupPos({ x: point.x, y: point.y });
    };

    updatePos();
    map.on("move zoom resize viewreset", updatePos);
    return () => {
      map.off("move zoom resize viewreset", updatePos);
    };
  }, [mapReady, draftPolygon, draftForm]);

  useEffect(() => {
    if (!mapReady) return;

    scheduleCamera(() => {
      const map = mapRef.current;
      if (!map) return;

      if (draftPolygon) {
        const bounds = draftBounds(draftPolygon);
        if (bounds) safeFitBounds(map, bounds, { maxZoom: 14 });
        return;
      }

      const focused =
        focusedAoiId != null
          ? aois.find((a) => a.properties.aoi_id === focusedAoiId)
          : null;

      if (focused) {
        const bounds = aoiPolygonBounds(focused);
        if (bounds) safeFitBounds(map, bounds, { maxZoom: 9 });
        return;
      }

      if (aois.length > 0 && !initialFitDoneRef.current) {
        const bounds = allAoisBounds(aois);
        if (bounds) {
          safeFitBounds(map, bounds, { maxZoom: 6 });
          initialFitDoneRef.current = true;
        }
      }
    });

    return cancelCameraFrame;
  }, [mapReady, focusedAoiId, draftPolygon, aois]);

  return (
    <div className="aoi-map-wrap">
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      {draftPolygon && draftForm && popupPos && (
        <div
          className="aoi-draft-popup-anchor"
          style={{ left: popupPos.x, top: popupPos.y }}
        >
          <AoiDraftPopup {...draftForm} />
        </div>
      )}
    </div>
  );
}
