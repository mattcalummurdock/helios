#!/usr/bin/env python3
"""Run inference on processed demo tiles and write detections to PostGIS (host-side fallback).

Use when Celery inference fails or for quick demo population:
  DATABASE_URL_SYNC=postgresql://helios:changeme@localhost:5433/helios
  TRITON_URL=localhost:8000
  PYTHONPATH=shared
  python ml/scripts/seed_demo_detections.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from helios_common.db import SyncSessionLocal
from helios_common.models import Detection, Scene
from helios_common.paths import scene_tiles_dir
from helios_common.triton_client import infer_yolo, nms_detections


def main() -> int:
    tiles_root = REPO_ROOT / "tiles"
    if not tiles_root.is_dir():
        tiles_root = Path("/tiles")

    with SyncSessionLocal() as session:
        scenes = session.execute(
            text("SELECT id, aoi_id FROM scenes WHERE processed = true ORDER BY id")
        ).fetchall()
        if not scenes:
            print("No processed scenes. Run seed_demo.py and preprocess first.")
            return 1

        total = 0
        for scene_id, aoi_id in scenes:
            tile_dir = tiles_root / str(scene_id)
            if not tile_dir.is_dir():
                tile_dir = Path(str(scene_tiles_dir(scene_id)))
            tiles = sorted(tile_dir.glob("*.tif"))
            if not tiles:
                print(f"Scene {scene_id}: no tiles in {tile_dir}")
                continue

            session.execute(text("DELETE FROM detections WHERE scene_id = :sid"), {"sid": scene_id})

            all_dets = []
            for tile in tiles:
                try:
                    all_dets.extend(infer_yolo(str(tile)))
                except Exception as exc:
                    print(f"  tile {tile.name}: {exc}")

            merged = nms_detections(all_dets, 0.45)
            now = datetime.now(timezone.utc)
            for det in merged:
                row = Detection(
                    scene_id=scene_id,
                    aoi_id=aoi_id,
                    class_=det.class_name,
                    confidence=det.confidence,
                    lat=det.lat,
                    lon=det.lon,
                    heading_degrees=det.heading_degrees,
                    bbox_polygon=WKTElement(det.bbox_wkt, srid=4326),
                    timestamp=now,
                )
                session.add(row)
                total += 1

            print(f"Scene {scene_id}: {len(merged)} detections from {len(tiles)} tiles")

        session.commit()
        print(f"Total detections written: {total}")
        return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
