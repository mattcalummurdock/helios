"use client";

import { demoExportExtension, exportDetections } from "@/lib/api";
import { isDemoMode } from "@/lib/demo";
import type { AoiFeature } from "@/lib/types";
import { useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  aois: AoiFeature[];
};

const FORMATS = ["pdf", "csv", "kml", "geojson"] as const;
const CLASSES = ["vehicle", "ship", "aircraft", "helicopter", "plane", "tank"];

export function ExportModal({ open, onClose, aois }: Props) {
  const [format, setFormat] = useState<(typeof FORMATS)[number]>("csv");
  const [aoiId, setAoiId] = useState<string>("");
  const [selectedClasses, setSelectedClasses] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const toggleClass = (cls: string) => {
    setSelectedClasses((prev) =>
      prev.includes(cls) ? prev.filter((c) => c !== cls) : [...prev, cls]
    );
  };

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    try {
      const blob = await exportDetections({
        format,
        aoi_id: aoiId ? Number(aoiId) : undefined,
        classes: selectedClasses.length ? selectedClasses : undefined,
      });
      const ext = isDemoMode() ? demoExportExtension(format) : format === "geojson" ? "geojson" : format;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `helios_export.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Export Data</h3>
        <label>Format</label>
        <select value={format} onChange={(e) => setFormat(e.target.value as typeof format)}>
          {FORMATS.map((f) => (
            <option key={f} value={f}>
              {f.toUpperCase()}
            </option>
          ))}
        </select>
        <label>AOI (optional)</label>
        <select value={aoiId} onChange={(e) => setAoiId(e.target.value)}>
          <option value="">All AOIs</option>
          {aois.map((a) => (
            <option key={a.properties.aoi_id} value={a.properties.aoi_id}>
              {a.properties.name}
            </option>
          ))}
        </select>
        <label>Classes</label>
        <div className="class-checkboxes">
          {CLASSES.map((cls) => (
            <label key={cls}>
              <input
                type="checkbox"
                checked={selectedClasses.includes(cls)}
                onChange={() => toggleClass(cls)}
              />
              {cls}
            </label>
          ))}
        </div>
        {error && <p style={{ color: "#e06c75", fontSize: "0.8rem", marginTop: "0.5rem" }}>{error}</p>}
        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" onClick={handleExport} disabled={loading}>
            {loading ? "Exporting…" : "Download"}
          </button>
        </div>
      </div>
    </div>
  );
}
