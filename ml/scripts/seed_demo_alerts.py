#!/usr/bin/env python3
"""Seed demo alerts from change events and a few standalone rules.

Usage:
  DATABASE_URL_SYNC=postgresql://helios:changeme@localhost:5433/helios
  PYTHONPATH=shared
  python ml/scripts/seed_demo_alerts.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from helios_common.db import SyncSessionLocal  # noqa: E402

_SEVERITY_FOR_CLASS = {
    "t62": "critical",
    "2s1": "critical",
    "an-26": "critical",
    "aircraft": "critical",
    "plane": "critical",
    "vehicle": "high",
    "btr_60": "high",
    "ship": "medium",
    "helicopter": "medium",
    "mi-8mt": "medium",
}


def _severity(subclass: str | None, cls: str | None) -> str:
    key = (subclass or cls or "").lower().replace("-", "_").replace(" ", "_")
    for token, sev in _SEVERITY_FOR_CLASS.items():
        if token in key:
            return sev
    if cls and cls.lower() in _SEVERITY_FOR_CLASS:
        return _SEVERITY_FOR_CLASS[cls.lower()]
    return "medium"


def main() -> int:
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        session.execute(text("DELETE FROM alerts"))
        session.execute(text("UPDATE change_events SET alert_fired = false"))
        session.commit()

        rows = session.execute(
            text(
                """
                SELECT ce.id, ce.aoi_id, ce.event_type::text, ce.distance_moved_m,
                       ce.bearing_degrees, ao.name AS aoi_name,
                       d1.lat AS t1_lat, d1.lon AS t1_lon,
                       d1.class AS t1_class, d1.subclass AS t1_subclass,
                       d2.lat AS t2_lat, d2.lon AS t2_lon,
                       d2.class AS t2_class, d2.subclass AS t2_subclass
                FROM change_events ce
                JOIN aois ao ON ao.id = ce.aoi_id
                LEFT JOIN detections d1 ON d1.id = ce.detection_id_t1
                LEFT JOIN detections d2 ON d2.id = ce.detection_id_t2
                ORDER BY ce.id
                """
            )
        ).fetchall()

        created: list[str] = []
        for row in rows:
            ce_id, aoi_id, event_type, dist, bearing, aoi_name = row[:6]
            t1_lat, t1_lon, t1_cls, t1_sub = row[6:10]
            t2_lat, t2_lon, t2_cls, t2_sub = row[10:14]

            if event_type == "moved" and t2_lat is not None:
                label = t2_sub or t2_cls or "object"
                alert_type = "movement_threshold"
                severity = _severity(t2_sub, t2_cls)
                if severity != "critical" and (dist or 0) >= 5000:
                    severity = "high"
                lat, lon = float(t2_lat), float(t2_lon)
                desc = (
                    f"{label} moved {dist:.0f}m at bearing {bearing or 0:.0f}° "
                    f"in {aoi_name}"
                )
            elif event_type == "appeared" and t2_lat is not None:
                label = t2_sub or t2_cls or "object"
                alert_type = "new_object"
                severity = _severity(t2_sub, t2_cls)
                lat, lon = float(t2_lat), float(t2_lon)
                desc = f"New {label} appeared in {aoi_name}"
            elif event_type == "disappeared" and t1_lat is not None:
                label = t1_sub or t1_cls or "object"
                alert_type = "disappearance"
                severity = _severity(t1_sub, t1_cls)
                lat, lon = float(t1_lat), float(t1_lon)
                desc = f"{label} no longer detected in {aoi_name}"
            else:
                continue

            session.execute(
                text(
                    """
                    INSERT INTO alerts (aoi_id, change_event_id, alert_type, severity,
                                        lat, lon, description, acknowledged, timestamp)
                    VALUES (:aoi, :ce, :atype, :sev, :lat, :lon, :desc, false, :ts)
                    """
                ),
                {
                    "aoi": aoi_id,
                    "ce": ce_id,
                    "atype": alert_type,
                    "sev": severity,
                    "lat": lat,
                    "lon": lon,
                    "desc": desc,
                    "ts": now,
                },
            )
            session.execute(
                text("UPDATE change_events SET alert_fired = true WHERE id = :id"),
                {"id": ce_id},
            )
            created.append(f"{aoi_name}: {alert_type} ({severity}) — {desc}")

        # Standalone coverage alert (no change event)
        stale = session.execute(
            text(
                """
                SELECT id, name,
                       ST_Y(ST_Centroid(polygon)) AS lat,
                       ST_X(ST_Centroid(polygon)) AS lon
                FROM aois WHERE monitoring_active = true ORDER BY id LIMIT 1
                """
            )
        ).first()
        if stale:
            session.execute(
                text(
                    """
                    INSERT INTO alerts (aoi_id, alert_type, severity, lat, lon,
                                        description, acknowledged, timestamp)
                    VALUES (:aoi, 'no_coverage', 'medium', :lat, :lon, :desc, false, :ts)
                    """
                ),
                {
                    "aoi": stale[0],
                    "lat": float(stale[2]),
                    "lon": float(stale[3]),
                    "desc": f"No fresh imagery for {stale[1]} — revisit window exceeded",
                    "ts": now,
                },
            )
            created.append(f"{stale[1]}: no_coverage (medium)")

        session.commit()
        print(f"Seeded {len(created)} alerts:")
        for line in created:
            print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
