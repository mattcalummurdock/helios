#!/usr/bin/env python3
"""Seed Helios demo: 3 regions, pre-staged DOTA satellite chips, real inference pipeline.

Prerequisites:
  1. python ml/scripts/download_dota.py
  2. python ml/scripts/pick_demo_images.py --apply
  3. Docker stack up (postgres, redis, triton, preprocessor, inference-service)
  4. DATABASE_URL_SYNC=postgresql://helios:changeme@localhost:5433/helios

Usage:
  python ml/scripts/seed_demo.py              # insert scenes + enqueue preprocessing
  python ml/scripts/seed_demo.py --dry-run    # show plan only
  python ml/scripts/seed_demo.py --local-paths  # use ./data and ./tiles (host paths)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text  # noqa: E402

from helios_common.db import SyncSessionLocal  # noqa: E402
from ml.scripts.demo_georef import jpg_to_sentinel_bands  # noqa: E402

MANIFEST = REPO_ROOT / "ml" / "demo_assets" / "manifest.json"

# AOI bounds (west, south, east, north) aligned with seeded migration AOIs + airfield hub
REGIONS = {
    "kyiv_vehicles": {
        "aoi_name": "Test AOI - Kyiv Region",
        "bounds": (30.40, 50.35, 30.60, 50.50),
        "asset_key": "vehicle",
        "external_id": "demo-kyiv-vehicles-t1",
        "minutes_ago": 120,
    },
    "kyiv_vehicles_t2": {
        "aoi_name": "Test AOI - Kyiv Region",
        "bounds": (30.40, 50.35, 30.60, 50.50),
        "asset_key": "vehicle_t2",
        "external_id": "demo-kyiv-vehicles-t2",
        "minutes_ago": 1,
    },
    "black_sea_ships": {
        "aoi_name": "Test AOI - Black Sea Port",
        "bounds": (30.60, 46.40, 30.80, 46.55),
        "asset_key": "ship",
        "external_id": "demo-black-sea-ships-t1",
        "minutes_ago": 90,
    },
    "airfield_aircraft": {
        "aoi_name": "Demo AOI - Airfield Hub",
        "bounds": (24.70, 49.80, 24.90, 49.95),
        "asset_key": "aircraft",
        "external_id": "demo-airfield-aircraft-t1",
        "minutes_ago": 60,
        "create_aoi": True,
        "aoi_wkt": "POLYGON((24.70 49.80, 24.90 49.80, 24.90 49.95, 24.70 49.95, 24.70 49.80))",
    },
}


def data_root(local_paths: bool) -> Path:
    return REPO_ROOT / "data" if local_paths else Path("/data")


def enqueue_preprocess(scene_id: int) -> None:
    from helios_common.celery_app import celery_app

    celery_app.send_task(
        "preprocessor.tasks.preprocess_scene",
        args=[scene_id],
        queue="preprocessing",
    )


def ensure_airfield_aoi(session) -> None:
    exists = session.execute(
        text("SELECT id FROM aois WHERE name = 'Demo AOI - Airfield Hub'")
    ).scalar()
    if exists:
        return
    session.execute(
        text(
            """
            INSERT INTO aois (name, priority, polygon, monitoring_active, last_pass_at)
            VALUES (
                'Demo AOI - Airfield Hub', 'high',
                ST_GeomFromText(:wkt, 4326), true, NOW()
            )
            """
        ),
        {"wkt": REGIONS["airfield_aircraft"]["aoi_wkt"]},
    )
    session.commit()
    print("Created AOI: Demo AOI - Airfield Hub")


def aoi_id_for_name(session, name: str) -> int:
    row = session.execute(text("SELECT id FROM aois WHERE name = :n"), {"n": name}).scalar()
    if not row:
        raise ValueError(f"AOI not found: {name}")
    return int(row)


def upsert_scene(
    session,
    *,
    aoi_id: int,
    external_id: str,
    scene_path: str,
    acquired_at: datetime,
) -> int:
    scene_id = session.execute(
        text(
            """
            INSERT INTO scenes (
                aoi_id, satellite_source, external_scene_id, sensor_type,
                acquisition_timestamp, cloud_cover_pct, scene_path, processed
            )
            VALUES (
                :aoi, 'copernicus', :ext, 'sentinel-2', :ts, 0.05, :path, false
            )
            ON CONFLICT (external_scene_id) DO UPDATE SET
                scene_path = EXCLUDED.scene_path,
                acquisition_timestamp = EXCLUDED.acquisition_timestamp,
                processed = false
            RETURNING id
            """
        ),
        {"aoi": aoi_id, "ext": external_id, "ts": acquired_at, "path": scene_path},
    ).scalar()
    session.commit()
    return int(scene_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Helios multi-region demo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--local-paths",
        action="store_true",
        help="Write under ./data (for host); Docker workers read the same mount",
    )
    parser.add_argument("--no-enqueue", action="store_true", help="Only prepare files + DB rows")
    args = parser.parse_args()

    if not MANIFEST.is_file():
        print(f"Missing {MANIFEST}. Run: python ml/scripts/pick_demo_images.py --apply")
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    copied = manifest.get("copied_files", {})
    root = data_root(args.local_paths)

    plan: list[dict] = []
    for region_key, cfg in REGIONS.items():
        asset_key = cfg["asset_key"]
        fname = copied.get(asset_key)
        if not fname:
            print(f"Missing copied asset for {asset_key}. Re-run pick_demo_images.py --apply")
            return 1
        jpg = REPO_ROOT / "ml" / "demo_assets" / fname
        plan.append({**cfg, "region_key": region_key, "jpg": str(jpg)})

    if args.dry_run:
        print(json.dumps(plan, indent=2, default=str))
        return 0

    with SyncSessionLocal() as session:
        ensure_airfield_aoi(session)

        scene_ids: list[int] = []
        now = datetime.now(timezone.utc)

        for item in plan:
            aoi_id = aoi_id_for_name(session, item["aoi_name"])
            # Placeholder path; updated after insert
            acquired = now - timedelta(minutes=item["minutes_ago"])
            scene_id = upsert_scene(
                session,
                aoi_id=aoi_id,
                external_id=item["external_id"],
                scene_path=str(root / "scenes" / "0" / "raw"),
                acquired_at=acquired,
            )

            raw_dir = root / "scenes" / str(scene_id) / "raw"
            jpg_to_sentinel_bands(Path(item["jpg"]), item["bounds"], raw_dir)

            session.execute(
                text("UPDATE scenes SET scene_path = :p WHERE id = :id"),
                {"p": str(raw_dir), "id": scene_id},
            )
            session.execute(
                text("UPDATE aois SET last_pass_at = :ts WHERE id = :id"),
                {"ts": acquired, "id": aoi_id},
            )
            session.commit()

            print(
                f"Scene {scene_id} ({item['external_id']}) "
                f"aoi={item['aoi_name']} <- {Path(item['jpg']).name}"
            )
            scene_ids.append(scene_id)

    if not args.no_enqueue:
        for sid in scene_ids:
            enqueue_preprocess(sid)
            print(f"Enqueued preprocess_scene(scene_id={sid})")
        print(
            "\nPipeline running in Docker. Watch: docker compose logs -f preprocessor inference-service"
        )
        print("Then open http://localhost:3000 and fly to Kyiv / Black Sea / Lviv airfield.")
    else:
        print("Scenes prepared (--no-enqueue). Trigger manually via Celery.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
