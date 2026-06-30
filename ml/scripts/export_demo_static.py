#!/usr/bin/env python3
"""Export seeded PostGIS demo data + detection images for static Vercel deploy.

Reads from DATABASE_URL_SYNC (default: localhost:5433) and writes:
  frontend/public/demo/data/*.json
  frontend/public/demo/images/detections/{id}/{crop|gradcam}.png

Usage:
  DATABASE_URL_SYNC=postgresql://helios:changeme@localhost:5433/helios
  python ml/scripts/export_demo_static.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from helios_common.geojson import aoi_feature, detection_feature, feature_collection  # noqa: E402
from helios_common.paths import resolve_detection_asset  # noqa: E402

OUT_ROOT = REPO_ROOT / "frontend" / "public" / "demo"
DATA_DIR = OUT_ROOT / "data"
IMG_DIR = OUT_ROOT / "images" / "detections"

_AOI_SELECT = """
    SELECT a.id, a.name, a.priority::text, a.last_pass_at, a.monitoring_active,
           ST_AsGeoJSON(a.polygon) AS geom,
           ls.satellite_source AS last_satellite_source,
           ls.cloud_cover_pct AS last_cloud_cover_pct,
           COALESCE(dc.cnt, 0) AS active_detection_count
    FROM aois a
    LEFT JOIN LATERAL (
        SELECT satellite_source, cloud_cover_pct
        FROM scenes
        WHERE aoi_id = a.id
        ORDER BY acquisition_timestamp DESC
        LIMIT 1
    ) ls ON true
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::int AS cnt
        FROM detections
        WHERE aoi_id = a.id
          AND timestamp >= NOW() - INTERVAL '7 days'
    ) dc ON true
    ORDER BY a.id
"""


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


def _copy_detection_images(session) -> int:
    rows = session.execute(
        text("SELECT id, detection_image_path, gradcam_path FROM detections ORDER BY id")
    ).mappings()
    copied = 0
    for row in rows:
        det_id = int(row["id"])
        for kind, col, filename in (
            ("crop", "detection_image_path", "crop.png"),
            ("gradcam", "gradcam_path", "gradcam.png"),
        ):
            src = resolve_detection_asset(row[col], det_id, filename)
            if src is None:
                continue
            dest = IMG_DIR / str(det_id) / f"{kind}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
            print(f"  image {det_id}/{kind}.png")
    return copied


def main() -> int:
    db_url = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://helios:changeme@localhost:5433/helios",
    )
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)

    print(f"Exporting demo static assets to {OUT_ROOT.relative_to(REPO_ROOT)}/")
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    if IMG_DIR.exists():
        shutil.rmtree(IMG_DIR)

    with Session() as session:
        aoi_rows = session.execute(text(_AOI_SELECT)).mappings()
        aoi_features = []
        for row in aoi_rows:
            aoi_features.append(
                aoi_feature(
                    aoi_id=row["id"],
                    polygon_geojson=json.loads(row["geom"]),
                    name=row["name"],
                    priority=row["priority"],
                    last_pass_at=row["last_pass_at"],
                    monitoring_active=row["monitoring_active"],
                    last_satellite_source=row["last_satellite_source"],
                    last_cloud_cover_pct=row["last_cloud_cover_pct"],
                    active_detection_count=row["active_detection_count"] or 0,
                )
            )
        _write_json(DATA_DIR / "aois.json", feature_collection(aoi_features))

        det_result = session.execute(
            text(
                """
                SELECT d.id, d.lat, d.lon, d.class, d.subclass, d.confidence, d.heading_degrees,
                       d.timestamp, d.scene_id, d.aoi_id, s.satellite_source,
                       ST_AsGeoJSON(d.bbox_polygon) AS bbox_geojson
                FROM detections d
                JOIN scenes s ON s.id = d.scene_id
                ORDER BY d.timestamp DESC
                """
            )
        ).mappings()
        det_features = []
        for row in det_result:
            bbox_gj = json.loads(row["bbox_geojson"]) if row["bbox_geojson"] else None
            det_features.append(
                detection_feature(
                    detection_id=row["id"],
                    lat=row["lat"],
                    lon=row["lon"],
                    class_name=row["class"],
                    confidence=row["confidence"],
                    timestamp=row["timestamp"],
                    subclass=row["subclass"],
                    heading_degrees=row["heading_degrees"],
                    scene_id=row["scene_id"],
                    aoi_id=row["aoi_id"],
                    satellite_source=row["satellite_source"],
                    bbox_geojson=bbox_gj,
                )
            )
        _write_json(DATA_DIR / "detections.json", feature_collection(det_features))

        change_result = session.execute(
            text(
                """
                SELECT ce.id, ce.aoi_id, ce.event_type::text, ce.distance_moved_m, ce.speed_kmh,
                       ce.bearing_degrees, ce.timestamp, ce.alert_fired,
                       d1.lat AS t1_lat, d1.lon AS t1_lon, d1.class AS t1_class,
                       d2.lat AS t2_lat, d2.lon AS t2_lon, d2.class AS t2_class
                FROM change_events ce
                LEFT JOIN detections d1 ON d1.id = ce.detection_id_t1
                LEFT JOIN detections d2 ON d2.id = ce.detection_id_t2
                ORDER BY ce.timestamp DESC
                """
            )
        ).mappings()
        events = []
        for row in change_result:
            events.append(
                {
                    "id": row["id"],
                    "aoi_id": row["aoi_id"],
                    "event_type": row["event_type"],
                    "distance_moved_m": row["distance_moved_m"],
                    "speed_kmh": row["speed_kmh"],
                    "bearing_degrees": row["bearing_degrees"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "alert_fired": row["alert_fired"],
                    "t1": (
                        {"lat": row["t1_lat"], "lon": row["t1_lon"], "class": row["t1_class"]}
                        if row["t1_lat"] is not None
                        else None
                    ),
                    "t2": (
                        {"lat": row["t2_lat"], "lon": row["t2_lon"], "class": row["t2_class"]}
                        if row["t2_lat"] is not None
                        else None
                    ),
                }
            )
        _write_json(DATA_DIR / "changes.json", {"events": events})

        alert_result = session.execute(
            text(
                """
                SELECT a.id, a.aoi_id, a.change_event_id, a.alert_type, a.severity::text,
                       a.lat, a.lon, a.description, a.acknowledged, a.acknowledged_by,
                       a.timestamp, ao.name AS aoi_name
                FROM alerts a
                JOIN aois ao ON ao.id = a.aoi_id
                ORDER BY a.timestamp DESC
                """
            )
        ).mappings()
        alerts = []
        for row in alert_result:
            alerts.append(
                {
                    "id": row["id"],
                    "aoi_id": row["aoi_id"],
                    "aoi_name": row["aoi_name"],
                    "change_event_id": row["change_event_id"],
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "description": row["description"],
                    "acknowledged": row["acknowledged"],
                    "acknowledged_by": row["acknowledged_by"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                }
            )
        _write_json(DATA_DIR / "alerts.json", {"alerts": alerts})

        scene_result = session.execute(
            text(
                """
                SELECT id, aoi_id, satellite_source, external_scene_id, sensor_type,
                       acquisition_timestamp, cloud_cover_pct, scene_path, processed, created_at
                FROM scenes
                ORDER BY acquisition_timestamp DESC
                """
            )
        ).mappings()
        scenes = []
        for row in scene_result:
            scenes.append(
                {
                    "id": row["id"],
                    "aoi_id": row["aoi_id"],
                    "satellite_source": row["satellite_source"],
                    "external_scene_id": row["external_scene_id"],
                    "sensor_type": row["sensor_type"],
                    "acquisition_timestamp": (
                        row["acquisition_timestamp"].isoformat()
                        if row["acquisition_timestamp"]
                        else None
                    ),
                    "cloud_cover_pct": row["cloud_cover_pct"],
                    "scene_path": row["scene_path"],
                    "processed": row["processed"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
            )
        _write_json(DATA_DIR / "scenes.json", {"scenes": scenes})

        img_count = _copy_detection_images(session)

    _write_json(
        DATA_DIR / "manifest.json",
        {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "aois": len(aoi_features),
            "detections": len(det_features),
            "changes": len(events),
            "alerts": len(alerts),
            "scenes": len(scenes),
            "images": img_count,
        },
    )

    print(
        f"\nDone: {len(aoi_features)} AOIs, {len(det_features)} detections, "
        f"{len(events)} changes, {len(alerts)} alerts, {img_count} images"
    )
    print("Deploy frontend on Vercel with NEXT_PUBLIC_DEMO_MODE=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
