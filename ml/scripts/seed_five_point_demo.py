#!/usr/bin/env python3
"""Five global showcase detections with distinct model designations (MSTAR + naval/air).

Subclass stores the specific model (T62, 2S1, …) — never DOTA coarse labels like
"plane" or "ship" that duplicate the MVP class.

Usage:
  DATABASE_URL_SYNC=postgresql://helios:changeme@localhost:5433/helios
  PYTHONPATH=shared
  python ml/scripts/seed_five_point_demo.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
from geoalchemy2.elements import WKTElement
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from helios_common.db import SyncSessionLocal  # noqa: E402
from helios_common.models import Detection  # noqa: E402
from ml.scripts.dota_hero import hero_from_jpg, mstar_grayscale_crop  # noqa: E402

DEMO_ASSETS = REPO_ROOT / "ml" / "demo_assets"

# MSTAR 8-class taxonomy (ml/artifacts/mstar/classes.txt)
MSTAR_MODELS = ("2S1", "BRDM_2", "BTR_60", "T62", "ZSU_23_4", "ZIL131", "D7", "SLICY")

# One marker each — coords chosen for terrain (ship on coastal water, not city center)
SHOWCASE = [
    {
        "label": "Kyiv armor column",
        "lat": 50.41,
        "lon": 30.45,
        "asset": "vehicle_P2048.jpg",
        "prefer_mvp": "vehicle",
        "mvp_class": "vehicle",
        "model": "T62",
        "scene_external_id": "demo-kyiv-vehicles-t1",
        "satellite_source": "copernicus",
    },
    {
        "label": "Black Sea anchorage",
        # Southern edge of Black Sea AOI — over water / port approach, not Odessa urban core
        "lat": 46.405,
        "lon": 30.74,
        "asset": "ship_P0838.jpg",
        "prefer_mvp": "ship",
        "mvp_class": "ship",
        "model": "Ropucha-class LST",
        "scene_external_id": "demo-black-sea-ships-t1",
        "satellite_source": "copernicus",
    },
    {
        "label": "Lviv airfield",
        "lat": 49.92,
        "lon": 24.78,
        "asset": "aircraft_P1397.jpg",
        "prefer_mvp": "aircraft",
        "mvp_class": "aircraft",
        "model": "An-26",
        "scene_external_id": "demo-airfield-aircraft-t1",
        "satellite_source": "copernicus",
    },
    {
        "label": "Baltic helipad",
        "lat": 59.43,
        "lon": 24.75,
        "asset": "helicopter_P1508.jpg",
        "prefer_mvp": "helicopter",
        "mvp_class": "helicopter",
        "model": "Mi-8MT",
        "scene_external_id": "demo-airfield-aircraft-t1",
        "satellite_source": "copernicus",
    },
    {
        "label": "Levant SAR pass",
        "lat": 34.55,
        "lon": 36.35,
        "asset": "vehicle_P2048.jpg",
        "prefer_mvp": "vehicle",
        "mvp_class": "vehicle",
        "model": "2S1",
        "scene_external_id": "demo-kyiv-vehicles-t1",
        "satellite_source": "sentinel-1",
        "sar_chip": True,
    },
]


def _scene_for_external(session, external_id: str) -> tuple[int, int]:
    row = session.execute(
        text("SELECT id, aoi_id FROM scenes WHERE external_scene_id = :ext"),
        {"ext": external_id},
    ).first()
    if not row:
        raise SystemExit(f"Scene not found: {external_id}. Run seed_demo.py first.")
    return int(row[0]), int(row[1])


def _save_crop(detection_id: int, crop_bgr) -> str:
    out_dir = REPO_ROOT / "data" / "detections" / str(detection_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "crop.png"
    cv2.imwrite(str(out), crop_bgr)
    return str(out)


def main() -> int:
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        session.execute(text("DELETE FROM detections"))
        session.commit()

        for item in SHOWCASE:
            jpg = DEMO_ASSETS / item["asset"]
            if not jpg.is_file():
                print(f"Missing asset: {jpg}")
                return 1

            scene_id, aoi_id = _scene_for_external(session, item["scene_external_id"])
            model = item["model"]
            mvp_class = item["mvp_class"]

            if item.get("sar_chip"):
                crop = mstar_grayscale_crop(jpg)
                confidence = 0.88
                heading = 0.0
            else:
                hero = hero_from_jpg(jpg, prefer_mvp=item.get("prefer_mvp"))
                if not hero:
                    print(f"No MVP detection in {item['asset']}")
                    return 1
                crop = hero.crop_bgr
                confidence = hero.confidence
                heading = hero.heading_degrees

            lat, lon = item["lat"], item["lon"]
            delta = 0.002
            wkt = (
                f"POLYGON(({lon - delta} {lat + delta}, {lon + delta} {lat + delta}, "
                f"{lon + delta} {lat - delta}, {lon - delta} {lat - delta}, "
                f"{lon - delta} {lat + delta}))"
            )

            row = Detection(
                scene_id=scene_id,
                aoi_id=aoi_id,
                class_=mvp_class,
                subclass=model,
                confidence=float(confidence),
                lat=float(lat),
                lon=float(lon),
                heading_degrees=float(heading),
                bbox_polygon=WKTElement(wkt, srid=4326),
                timestamp=now,
            )
            session.add(row)
            session.flush()

            crop_path = _save_crop(row.id, crop)
            row.detection_image_path = crop_path
            row.gradcam_path = None

            print(
                f"  #{row.id} {item['label']}: class={mvp_class} model={model} "
                f"@ ({lat}, {lon})"
            )

        session.commit()

    print("\n5 showcase detections written. Refresh the globe (localhost:3001).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
