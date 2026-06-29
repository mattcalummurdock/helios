"use client";

import { useEffect, useState } from "react";
import { fetchDetectionImageBlob } from "@/lib/api";
import { detectionModelLabel } from "@/lib/detection-display";
import type { DetectionFeature } from "@/lib/types";

type Props = {
  detection: DetectionFeature | null;
  onClose: () => void;
};

export function DetectionPanel({ detection, onClose }: Props) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageLabel, setImageLabel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!detection) {
      setImageUrl(null);
      setImageLabel(null);
      setLoading(false);
      return;
    }

    let revoked: string | null = null;
    let cancelled = false;
    const detectionId = detection.properties.detection_id;

    setLoading(true);
    setImageUrl(null);
    setImageLabel(null);

    (async () => {
      for (const kind of ["crop", "gradcam"] as const) {
        const blob = await fetchDetectionImageBlob(detectionId, kind);
        if (cancelled) return;
        if (blob) {
          revoked = URL.createObjectURL(blob);
          setImageUrl(revoked);
          setImageLabel(kind === "gradcam" ? "Grad-CAM heatmap" : "Satellite crop");
          break;
        }
      }
      if (!cancelled) setLoading(false);
    })();

    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [detection?.properties.detection_id]);

  if (!detection) return null;
  const p = detection.properties;
  const model = detectionModelLabel(p.class, p.subclass);

  return (
    <div className="panel detection-panel">
      <button className="panel-close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <h3>
        Detection #{p.detection_id}
        {model ? ` — ${model}` : ""}
      </h3>
      <div className="row">
        <span>Class</span>
        <span>{p.class}</span>
      </div>
      {model && (
        <div className="row">
          <span>Model</span>
          <span>{model}</span>
        </div>
      )}
      <div className="row">
        <span>Confidence</span>
        <span>{(p.confidence * 100).toFixed(1)}%</span>
      </div>
      <div className="row">
        <span>Coordinates</span>
        <span>
          {p.lat.toFixed(6)}, {p.lon.toFixed(6)}
        </span>
      </div>
      {p.heading_degrees != null && (
        <div className="row">
          <span>Heading</span>
          <span>{p.heading_degrees.toFixed(1)}°</span>
        </div>
      )}
      <div className="row">
        <span>Timestamp</span>
        <span>{new Date(p.timestamp).toLocaleString()}</span>
      </div>
      <div className="row">
        <span>Source</span>
        <span>{p.satellite_source || "—"}</span>
      </div>
      {loading && (
        <p className="meta" style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#5c7a8a" }}>
          Loading image…
        </p>
      )}
      {!loading && imageUrl && (
        <img src={imageUrl} alt={imageLabel || "Detection image"} className="gradcam" />
      )}
      {!loading && !imageUrl && (
        <p className="meta" style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#5c7a8a" }}>
          No crop or Grad-CAM image available for this detection
        </p>
      )}
    </div>
  );
}
