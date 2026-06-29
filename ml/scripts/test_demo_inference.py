#!/usr/bin/env python3
"""Run YOLO inference on demo asset JPGs (Ultralytics + Triton) and report MVP classes."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

MANIFEST = REPO_ROOT / "ml" / "demo_assets" / "manifest.json"
MVP_FROM_DOTA = {
    "plane": "aircraft",
    "ship": "ship",
    "large-vehicle": "vehicle",
    "small-vehicle": "vehicle",
    "helicopter": "helicopter",
}


def ultralytics_summary(model, path: Path, conf: float) -> str:
    result = model.predict(str(path), conf=conf, verbose=False)[0]
    obb = result.obb
    if obb is None or len(obb) == 0:
        return "0 detections"
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
        return "0 MVP-class detections"
    return ", ".join(f"{k}={v} (max {max_conf[k]:.2f})" for k, v in sorted(counts.items()))


def triton_summary(path: Path) -> str:
    import os

    from helios_common.triton_client import infer_yolo

    os.environ.setdefault("TRITON_URL", "localhost:8000")
    try:
        dets = infer_yolo(str(path))
    except Exception as exc:
        return f"ERROR: {exc}"
    if not dets:
        return "0 detections"
    counts: dict[str, int] = defaultdict(int)
    max_conf: dict[str, float] = defaultdict(float)
    for d in dets:
        counts[d.class_name] += 1
        max_conf[d.class_name] = max(max_conf[d.class_name], d.confidence)
    return ", ".join(f"{k}={v} (max {max_conf[k]:.2f})" for k, v in sorted(counts.items()))


def main() -> int:
    if not MANIFEST.is_file():
        print("Run: python ml/scripts/pick_demo_images.py --apply")
        return 1

    from ultralytics import YOLO

    weights = REPO_ROOT / "ml" / "artifacts" / "yolo" / "best.pt"
    model = YOLO(str(weights))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    print(f"{'Asset':<14} {'File':<28} Ultralytics (best.pt)          Triton ONNX")
    print("-" * 95)
    for key, fname in manifest.get("copied_files", {}).items():
        path = REPO_ROOT / "ml" / "demo_assets" / fname
        if not path.is_file():
            print(f"{key:<14} MISSING {fname}")
            continue
        u = ultralytics_summary(model, path, 0.25)
        t = triton_summary(path)
        print(f"{key:<14} {fname:<28} {u:<30} {t}")

    print("\nSelection uses Ultralytics (training checkpoint). Triton is the production serving path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
