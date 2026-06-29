"use client";

import { getAlerts } from "@/lib/api";
import type { Alert, AoiFeature } from "@/lib/types";
import { useCallback, useEffect, useMemo, useState } from "react";

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2 };

type Props = {
  open: boolean;
  onClose: () => void;
  aois: AoiFeature[];
  onFlyTo: (lat: number, lon: number) => void;
  onCountChange?: (count: number) => void;
  externalAlerts?: Alert[];
};

export function AlertPanel({
  open,
  onClose,
  aois,
  onFlyTo,
  onCountChange,
  externalAlerts = [],
}: Props) {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  const aoiNameMap = useMemo(() => {
    const m = new Map<number, string>();
    aois.forEach((a) => m.set(a.properties.aoi_id, a.properties.name));
    return m;
  }, [aois]);

  const loadAlerts = useCallback(async () => {
    const data = await getAlerts();
    setAlerts(data.alerts);
    onCountChange?.(data.alerts.length);
  }, [onCountChange]);

  useEffect(() => {
    onCountChange?.(alerts.length);
  }, [alerts.length, onCountChange]);

  useEffect(() => {
    loadAlerts().catch(console.error);
    if (typeof window !== "undefined" && "Notification" in window) {
      Notification.requestPermission().catch(() => {});
    }
  }, [loadAlerts]);

  useEffect(() => {
    if (externalAlerts.length === 0) return;
    setAlerts((prev) => {
      const ids = new Set(prev.map((a) => a.id));
      const merged = [...externalAlerts.filter((a) => !ids.has(a.id)), ...prev];
      const sorted = merged.sort((a, b) => {
        const sd =
          (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
        if (sd !== 0) return sd;
        return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
      });
      onCountChange?.(sorted.length);
      return sorted;
    });
    const latest = externalAlerts[0];
    if (latest?.severity === "critical" && Notification.permission === "granted") {
      new Notification("Helios Critical Alert", {
        body: latest.description,
      });
    }
  }, [externalAlerts]);

  return (
    <div className={`alert-panel panel ${open ? "open" : ""}`}>
      <div className="alert-panel-header">
        <h3>Alerts</h3>
        <button className="panel-close" onClick={onClose}>
          ×
        </button>
      </div>
        <div className="alert-panel-list">
          {alerts.length === 0 && (
            <p style={{ color: "#5c7a8a", fontSize: "0.85rem", padding: "0.5rem" }}>
              No alerts
            </p>
          )}
          {alerts.map((alert) => (
            <div key={alert.id} className={`alert-card severity-${alert.severity}`}>
              <span className={`severity-badge severity-${alert.severity}`}>
                {alert.severity.toUpperCase()}
              </span>
              <div style={{ fontSize: "0.8rem", fontWeight: 600 }}>{alert.alert_type}</div>
              <div style={{ fontSize: "0.75rem", color: "#5c7a8a", margin: "0.25rem 0" }}>
                {alert.aoi_name || aoiNameMap.get(alert.aoi_id) || `AOI ${alert.aoi_id}`}
              </div>
              <div style={{ fontSize: "0.8rem" }}>{alert.description}</div>
              <div style={{ fontSize: "0.7rem", color: "#5c7a8a", marginTop: "0.25rem" }}>
                {new Date(alert.timestamp).toLocaleString()}
              </div>
              <div className="alert-card-actions">
                <button onClick={() => onFlyTo(alert.lat, alert.lon)}>Fly To</button>
              </div>
            </div>
          ))}
        </div>
      </div>
  );
}
