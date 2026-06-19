#!/usr/bin/env python3
"""Convert DOTA polygon annotations to YOLO OBB format with scene-level split."""

from __future__ import annotations

import argparse
import math
import random
import shutil
from pathlib import Path

import yaml

from ml.paths import CONFIGS_DIR, DATASETS_DIR, DOTA_CATEGORY_MAP, DOTA_CLASSES

SPLITS = ("train", "val", "test")


def parse_dota_line(line: str) -> tuple[str, list[tuple[float, float]]] | None:
    parts = line.strip().split()
    if len(parts) < 9:
        return None
    coords = [float(x) for x in parts[:8]]
    category = parts[8]
    points = [(coords[i], coords[i + 1]) for i in range(0, 8, 2)]
    return category, points


def polygon_to_obb(points: list[tuple[float, float]], img_w: int, img_h: int) -> tuple[float, float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    angle = math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0])
    return cx / img_w, cy / img_h, w / img_w, h / img_h, angle


def scene_id_from_name(name: str) -> str:
    """Group tiles by source scene (strip trailing _patch index if present)."""
    stem = Path(name).stem
    if "_" in stem:
        parts = stem.rsplit("_", 1)
        if parts[-1].isdigit():
            return parts[0]
    return stem


def convert_split(
    src_images: Path,
    src_labels: Path,
    dst_root: Path,
    split: str,
    scene_ids: set[str],
) -> int:
    count = 0
    img_out = dst_root / split / "images"
    lbl_out = dst_root / split / "labels"
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    for label_path in src_labels.glob("*.txt"):
        sid = scene_id_from_name(label_path.stem)
        if sid not in scene_ids:
            continue

        img_path = src_images / f"{label_path.stem}.png"
        if not img_path.exists():
            img_path = src_images / f"{label_path.stem}.jpg"
        if not img_path.exists():
            continue

        lines_out: list[str] = []
        with open(label_path, encoding="utf-8") as f:
            for line in f:
                parsed = parse_dota_line(line)
                if not parsed:
                    continue
                category, points = parsed
                mapped = DOTA_CATEGORY_MAP.get(category)
                if mapped is None:
                    continue
                cls_id = DOTA_CLASSES.index(mapped)
                try:
                    from PIL import Image

                    with Image.open(img_path) as im:
                        w, h = im.size
                except Exception:
                    w, h = 4096, 4096
                cx, cy, bw, bh, ang = polygon_to_obb(points, w, h)
                lines_out.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f} {ang:.6f}")

        if not lines_out:
            continue

        shutil.copy2(img_path, img_out / img_path.name)
        with open(lbl_out / f"{label_path.stem}.txt", "w", encoding="utf-8") as out:
            out.write("\n".join(lines_out) + "\n")
        count += 1
    return count


def collect_scenes(raw_dirs: list[Path]) -> list[str]:
    scenes: set[str] = set()
    for raw in raw_dirs:
        label_dir = raw / "labelTxt"
        if not label_dir.exists():
            label_dir = raw / "labelTxt-v1.0"
        if not label_dir.exists():
            continue
        for lbl in label_dir.glob("*.txt"):
            scenes.add(scene_id_from_name(lbl.stem))
    return sorted(scenes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DATASETS_DIR / "dota_raw")
    parser.add_argument("--output", type=Path, default=DATASETS_DIR / "dota")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    raw_dirs = [args.raw / "train", args.raw / "val"]
    scenes = collect_scenes(raw_dirs)
    if not scenes:
        raise SystemExit(f"No DOTA labels found under {args.raw}")

    rng = random.Random(args.seed)
    rng.shuffle(scenes)
    n = len(scenes)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    train_scenes = set(scenes[:n_train])
    val_scenes = set(scenes[n_train : n_train + n_val])
    test_scenes = set(scenes[n_train + n_val :])

    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    totals = {}
    for split, scene_set, raw in [
        ("train", train_scenes, args.raw / "train"),
        ("val", val_scenes, args.raw / "val"),
        ("test", test_scenes, args.raw / "val"),
    ]:
        img_dir = raw / "images"
        lbl_dir = raw / "labelTxt"
        if not lbl_dir.exists():
            lbl_dir = raw / "labelTxt-v1.0"
        totals[split] = convert_split(img_dir, lbl_dir, args.output, split, scene_set)

    yaml_path = CONFIGS_DIR / "dota_mvp.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = {
        "path": str(args.output.resolve()),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "names": {i: name for i, name in enumerate(DOTA_CLASSES)},
        "nc": len(DOTA_CLASSES),
    }
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    print(f"Scene split: train={len(train_scenes)} val={len(val_scenes)} test={len(test_scenes)}")
    print(f"Images: {totals}")
    print(f"Wrote {yaml_path}")


if __name__ == "__main__":
    main()
