"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  db?: string;
  phase?: number;
  error?: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data: HealthResponse) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        setHealth({ status: "error", error: "Cannot reach API" });
        setLoading(false);
      });
  }, []);

  const statusClass =
    health?.status === "ok"
      ? "status-ok"
      : health?.status === "error"
        ? "status-error"
        : "status-pending";

  return (
    <main>
      <h1>Helios MVP</h1>
      <p className="subtitle">Phase 1 — Infrastructure &amp; Environment Setup</p>

      <div className="card">
        <h2>API Health</h2>
        {loading ? (
          <p className="status-pending">Checking...</p>
        ) : (
          <>
            <p className={statusClass}>
              Status: {health?.status ?? "unknown"}
              {health?.db ? ` | DB: ${health.db}` : ""}
            </p>
            {health?.error && <p className="detail">{health.error}</p>}
            <p className="detail">Endpoint: {API_URL}/health</p>
          </>
        )}
      </div>

      <div className="card">
        <h2>Services (Phase 1)</h2>
        <ul className="services">
          <li>postgres — PostGIS 15</li>
          <li>redis — Celery broker</li>
          <li>triton — GPU inference server</li>
          <li>scene-watcher — Celery Beat + scene_watch queue</li>
          <li>preprocessor — preprocessing queue</li>
          <li>inference-service — inference queue</li>
          <li>change-detection — change_detection queue</li>
          <li>alert-service — alert scan worker</li>
          <li>fastapi — REST API</li>
          <li>frontend — this page</li>
        </ul>
      </div>

      <div className="card">
        <h2>Next Steps</h2>
        <p className="detail">
          Phase 2: Satellite data ingestion &amp; preprocessing pipeline
        </p>
      </div>
    </main>
  );
}
