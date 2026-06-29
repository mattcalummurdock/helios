"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createAoi,
  deactivateAoi,
  getAois,
  updateAoi,
} from "@/lib/api";
import type { AoiFeature } from "@/lib/types";

const AoiDrawMap = dynamic(() => import("@/components/aois/AoiDrawMap").then((m) => m.AoiDrawMap), {
  ssr: false,
  loading: () => <div className="auth-loading">Loading map…</div>,
});

export default function AoiManagerPage() {
  const [aois, setAois] = useState<AoiFeature[]>([]);
  const [name, setName] = useState("");
  const [priority, setPriority] = useState<"high" | "medium" | "low">("medium");
  const [polygon, setPolygon] = useState<number[][][] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [focusedAoiId, setFocusedAoiId] = useState<number | null>(null);

  const loadAois = useCallback(async () => {
    const data = await getAois();
    setAois(data.features);
  }, []);

  useEffect(() => {
    loadAois().catch(console.error);
  }, [loadAois]);

  const clearDraft = useCallback(() => {
    setName("");
    setPolygon(null);
    setError(null);
    setPriority("medium");
  }, []);

  const handleSave = useCallback(async () => {
    if (!name.trim() || !polygon) {
      setError("Enter a name for this AOI");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createAoi({
        name: name.trim(),
        priority,
        geometry: { type: "Polygon", coordinates: polygon },
      });
      clearDraft();
      setFocusedAoiId(null);
      await loadAois();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create AOI");
    } finally {
      setSaving(false);
    }
  }, [name, polygon, priority, clearDraft, loadAois]);

  const handleToggle = async (aoi: AoiFeature) => {
    setFocusedAoiId(aoi.properties.aoi_id);
    await updateAoi(aoi.properties.aoi_id, {
      monitoring_active: !aoi.properties.monitoring_active,
    });
    await loadAois();
  };

  const handlePolygonDrawn = useCallback((coords: number[][][] | null) => {
    setFocusedAoiId(null);
    setError(null);
    setName("");
    setPolygon(coords);
  }, []);

  const handleDrawStart = useCallback(() => {
    setFocusedAoiId(null);
    setPolygon(null);
    setError(null);
    setName("");
  }, []);

  const handleDelete = async (id: number) => {
    await deactivateAoi(id);
    setDeleteConfirm(null);
    setFocusedAoiId(id);
    await loadAois();
  };

  const draftForm = useMemo(
    () =>
      polygon
        ? {
            name,
            priority,
            saving,
            error,
            onNameChange: setName,
            onPriorityChange: setPriority,
            onSave: handleSave,
            onCancel: clearDraft,
          }
        : null,
    [polygon, name, priority, saving, error, clearDraft, handleSave]
  );

  return (
    <div className="aoi-page">
      <div className="aoi-list-panel">
        <h2 style={{ color: "#7fdbca", marginBottom: "1rem", fontSize: "1rem" }}>Areas of Interest</h2>
        {aois.length === 0 && (
          <p style={{ color: "#5c7a8a", fontSize: "0.85rem" }}>No AOIs defined yet</p>
        )}
        {aois.map((aoi) => (
          <div
            key={aoi.properties.aoi_id}
            className={`aoi-list-item ${aoi.properties.monitoring_active ? "" : "inactive"}`}
            onClick={() => setFocusedAoiId(aoi.properties.aoi_id)}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h4>{aoi.properties.name}</h4>
              <label className="toggle-switch" title="Monitoring active" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={aoi.properties.monitoring_active}
                  onChange={() => handleToggle(aoi)}
                />
                <span className="toggle-slider" />
              </label>
            </div>
            <div className="meta">
              Priority: {aoi.properties.priority}
              <br />
              Last pass:{" "}
              {aoi.properties.last_pass_at
                ? new Date(aoi.properties.last_pass_at).toLocaleString()
                : "Never"}
              <br />
              Detections (7d): {aoi.properties.active_detection_count ?? 0}
            </div>
            <button
              style={{
                marginTop: "0.5rem",
                fontSize: "0.75rem",
                color: "#e06c75",
                background: "none",
                border: "1px solid #e06c75",
                borderRadius: "4px",
                padding: "0.25rem 0.5rem",
                cursor: "pointer",
              }}
              onClick={(e) => {
                e.stopPropagation();
                setDeleteConfirm(aoi.properties.aoi_id);
              }}
            >
              Deactivate
            </button>
          </div>
        ))}
      </div>

      <div className="aoi-map-panel">
        <div className="aoi-map-hint">
          Use the <strong>polygon tool</strong> on the map to draw a new AOI. A form will appear on the shape.
        </div>
        <div className="aoi-map-container">
          <AoiDrawMap
            aois={aois}
            focusedAoiId={focusedAoiId}
            draftPolygon={polygon}
            draftForm={draftForm}
            onDrawStart={handleDrawStart}
            onPolygonDrawn={handlePolygonDrawn}
          />
        </div>
      </div>

      {deleteConfirm != null && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Deactivate AOI?</h3>
            <p style={{ fontSize: "0.85rem", margin: "0.75rem 0" }}>
              This stops monitoring but keeps historical detections.
            </p>
            <div className="modal-actions">
              <button onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button className="primary" onClick={() => handleDelete(deleteConfirm)}>
                Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
