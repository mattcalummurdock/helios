#!/usr/bin/env python3
"""Scan DOTA val/test images with the trained YOLO-OBB model and pick demo candidates.

Image requirements for Helios optical inference:
  - Top-down / nadir satellite or airborne survey (not oblique photos)
  - RGB, roughly 640–4000 px (pipeline tiles to 640×640)
  - Objects at satellite scale: vehicles, ships, aircraft, helicopters

Recommended source (already in repo):
  - DOTA v1.0: https://github.com/ultralytics/assets/releases/download/v0.0.0/DOTAv1.zip
  - Official page: https://captain-whu.github.io/DOTA/dataset.html

Alternatives:
  - xView: https://xview-dataset.org/
  - DIOR: https://gcheng-nwpu.github.io/#Dior
  - Copernicus Sentinel-2 (real passes, lower resolution): https://dataspace.copernicus.eu/

Usage:
  python ml/scripts/pick_demo_images.py
  python ml/scripts/pick_demo_images.py --apply   # copy winners to ml/demo_assets/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.paths import ARTIFACTS_DIR, DATASETS_DIR, DOTA_CATEGORY_MAP  # noqa: E402

# DOTA native class names (15-class model) → Helios MVP labels
MVP_FROM_DOTA = {
    "plane": "aircraft",
    "ship": "ship",
    "large-vehicle": "vehicle",
    "small-vehicle": "vehicle",
    "helicopter": "helicopter",
}

# Curated fallbacks if scan finds nothing (validated on val split)
DEFAULT_PICKS = {
    "vehicle": {
        "file": "P2625.jpg",
        "split": "val",
        "notes": "Dense large-vehicle parking lot (~270 detections @ conf 0.25)",
    },
    "vehicle_t2": {
        "file": "P2082.jpg",
        "split": "val",
        "notes": "Second vehicle-heavy pass for T1/T2 change demo",
    },
    "ship": {
        "file": "P0838.jpg",
        "split": "val",
        "notes": "Harbor with ~297 ship detections (validated via Triton)",
    },
    "aircraft": {
        "file": "P1397.jpg",
        "split": "val",
        "notes": "Airfield with ~300 plane detections (validated via Triton)",
    },
    "helicopter": {
        "file": "P1508.jpg",
        "split": "val",
        "notes": "Helipad cluster (~15 helicopters)",
    },
}

DEMO_ASSETS = REPO_ROOT / "ml" / "demo_assets"
MANIFEST_PATH = DEMO_ASSETS / "manifest.json"


def dota_image_roots() -> list[Path]:
    base = DATASETS_DIR / "dota" / "DOTAv1" / "images"
    roots = []
    for split in ("val", "test", "train"):
        d = base / split
        if d.is_dir():
            roots.append(d)
    return roots


def scan_images(model, image_dirs: list[Path], conf: float, limit: int | None) -> dict[str, list[dict]]:
    """Return best-scoring images per MVP class."""
    per_mvp: dict[str, list[dict]] = defaultdict(list)

    for img_dir in image_dirs:
        imgs = sorted(img_dir.glob("*.jpg"))
        if limit:
            imgs = imgs[:limit]
        for img_path in imgs:
            result = model.predict(str(img_path), conf=conf, verbose=False)[0]
            obb = result.obb
            if obb is None or len(obb) == 0:
                continue

            counts: dict[str, int] = defaultdict(int)
            max_conf: dict[str, float] = defaultdict(float)
            for box in obb:
                dota_name = result.names[int(box.cls)]
                mvp = MVP_FROM_DOTA.get(dota_name)
                if not mvp:
                    continue
                c = float(box.conf)
                counts[mvp] += 1
                max_conf[mvp] = max(max_conf[mvp], c)

            if not counts:
                continue

            for mvp, n in counts.items():
                per_mvp[mvp].append(
                    {
                        "mvp_class": mvp,
                        "file": img_path.name,
                        "split": img_dir.name,
                        "path": str(img_path.resolve()),
                        "count": n,
                        "max_conf": round(max_conf[mvp], 4),
                        "total_mvp_dets": sum(counts.values()),
                    }
                )

    for mvp in per_mvp:
        per_mvp[mvp].sort(key=lambda r: (-r["count"], -r["max_conf"]))
    return per_mvp


def pick_winners(per_mvp: dict[str, list[dict]]) -> dict[str, dict]:
    winners: dict[str, dict] = {}
    for mvp in ("vehicle", "ship", "aircraft", "helicopter"):
        if per_mvp.get(mvp):
            winners[mvp] = per_mvp[mvp][0]
        elif mvp in DEFAULT_PICKS:
            fb = DEFAULT_PICKS[mvp]
            src = DATASETS_DIR / "dota" / "DOTAv1" / "images" / fb["split"] / fb["file"]
            winners[mvp] = {
                "mvp_class": mvp,
                "file": fb["file"],
                "split": fb["split"],
                "path": str(src.resolve()),
                "count": None,
                "max_conf": None,
                "notes": fb["notes"],
                "fallback": True,
            }
    # T2 vehicle pass (different image, same demo story)
    fb = DEFAULT_PICKS["vehicle_t2"]
    src = DATASETS_DIR / "dota" / "DOTAv1" / "images" / fb["split"] / fb["file"]
    winners["vehicle_t2"] = {
        "mvp_class": "vehicle",
        "file": fb["file"],
        "split": fb["split"],
        "path": str(src.resolve()),
        "role": "t2_change_pass",
        "notes": fb["notes"],
    }
    return winners


def apply_assets(winners: dict[str, dict]) -> None:
    DEMO_ASSETS.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for key, row in winners.items():
        src = Path(row["path"])
        if not src.is_file():
            print(f"SKIP missing: {src}")
            continue
        dest_name = f"{key}_{row['file']}"
        dest = DEMO_ASSETS / dest_name
        shutil.copy2(src, dest)
        copied[key] = dest_name
        print(f"Copied {src.name} -> {dest}")

    manifest = {
        "source": "DOTA v1.0 (Ultralytics pack)",
        "source_urls": [
            "https://github.com/ultralytics/assets/releases/download/v0.0.0/DOTAv1.zip",
            "https://captain-whu.github.io/DOTA/dataset.html",
        ],
        "image_requirements": {
            "view": "top-down satellite / aerial survey",
            "format": "RGB JPG or GeoTIFF (3-band Sentinel-style for pipeline)",
            "tile_size": 640,
            "classes": list(MVP_FROM_DOTA.values()),
        },
        "winners": winners,
        "copied_files": copied,
        "demo_aoi_mapping": {
            "kyiv_vehicles_t1": "vehicle",
            "kyiv_vehicles_t2": "vehicle_t2",
            "black_sea_ships": "ship",
            "airfield_aircraft": "aircraft",
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nWrote {MANIFEST_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pick DOTA images for Helios demo")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=None, help="Max images per split (default: all val/test)")
    parser.add_argument("--apply", action="store_true", help="Copy winners to ml/demo_assets/")
    args = parser.parse_args()

    weights = ARTIFACTS_DIR / "yolo" / "best.pt"
    if not weights.is_file():
        print(f"Missing weights: {weights}")
        print("Train first: python ml/scripts/train_yolov8.py")
        return 1

    roots = dota_image_roots()
    if not roots:
        print("DOTA not found. Run: python ml/scripts/download_dota.py")
        return 1

    from ultralytics import YOLO

    model = YOLO(str(weights))
    print(f"Model: {weights.name}  task={model.task}  conf>={args.conf}")
    print(f"Scanning: {[str(r) for r in roots]}")

    per_mvp = scan_images(model, roots, args.conf, args.limit)
    winners = pick_winners(per_mvp)

    print("\n=== Top candidates per MVP class ===")
    for mvp in ("vehicle", "ship", "aircraft", "helicopter"):
        rows = per_mvp.get(mvp, [])[:5]
        print(f"\n{mvp}:")
        if not rows:
            print("  (no scan hits — using fallback)")
        for r in rows:
            print(
                f"  {r['file']} [{r['split']}]  count={r['count']}  "
                f"max_conf={r['max_conf']}  path={r['path']}"
            )

    print("\n=== Selected for demo ===")
    for key, row in winners.items():
        extra = f"  ({row['notes']})" if row.get("notes") else ""
        cnt = row.get("count")
        conf = row.get("max_conf")
        stats = f"count={cnt} max_conf={conf}" if cnt is not None else "fallback"
        print(f"  {key}: {row['file']} [{row.get('split')}] {stats}{extra}")

    if args.apply:
        apply_assets(winners)
    else:
        print("\nRun with --apply to copy files to ml/demo_assets/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
