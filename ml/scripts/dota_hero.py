"""Pick one hero detection + crop from a DOTA demo JPG using the trained YOLO-OBB model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

MVP_FROM_DOTA = {
    "plane": "aircraft",
    "ship": "ship",
    "large-vehicle": "vehicle",
    "small-vehicle": "vehicle",
    "helicopter": "helicopter",
}


@dataclass
class HeroDetection:
    mvp_class: str
    subclass: str
    confidence: float
    heading_degrees: float
    crop_bgr: np.ndarray


def hero_from_jpg(jpg_path: Path, *, prefer_mvp: str | None = None) -> HeroDetection | None:
    from ultralytics import YOLO

    repo = Path(__file__).resolve().parents[2]
    weights = repo / "ml" / "artifacts" / "yolo" / "best.pt"
    if not weights.is_file():
        raise FileNotFoundError(f"Missing YOLO weights: {weights}")

    img = cv2.imread(str(jpg_path))
    if img is None:
        raise FileNotFoundError(jpg_path)

    model = YOLO(str(weights))
    result = model.predict(str(jpg_path), conf=0.25, verbose=False)[0]
    obb = result.obb
    if obb is None or len(obb) == 0:
        return None

    best_idx = None
    best_score = -1.0
    for i, box in enumerate(obb):
        dota_name = result.names[int(box.cls)]
        mvp = MVP_FROM_DOTA.get(dota_name)
        if not mvp:
            continue
        if prefer_mvp and mvp != prefer_mvp:
            continue
        conf = float(box.conf)
        if conf > best_score:
            best_score = conf
            best_idx = i

    if best_idx is None:
        for i, box in enumerate(obb):
            dota_name = result.names[int(box.cls)]
            if dota_name not in MVP_FROM_DOTA:
                continue
            conf = float(box.conf)
            if conf > best_score:
                best_score = conf
                best_idx = i

    if best_idx is None:
        return None

    box = obb[best_idx]
    dota_name = result.names[int(box.cls)]
    mvp = MVP_FROM_DOTA[dota_name]
    h_img, w_img = img.shape[:2]
    xyxy = box.xyxy.cpu().numpy().astype(int)[0]
    x1, y1, x2, y2 = (
        max(0, xyxy[0]),
        max(0, xyxy[1]),
        min(w_img, xyxy[2]),
        min(h_img, xyxy[3]),
    )
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        crop = img

    angle = float(box.xywhr.cpu().numpy()[0][4]) if hasattr(box, "xywhr") else 0.0
    return HeroDetection(
        mvp_class=mvp,
        subclass=dota_name,
        confidence=float(box.conf),
        heading_degrees=np.degrees(angle) % 360,
        crop_bgr=crop,
    )


def mstar_grayscale_crop(jpg_path: Path) -> np.ndarray:
    """SAR-style grayscale chip for MSTAR-labelled demo (when chips not on disk)."""
    img = cv2.imread(str(jpg_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(jpg_path)
    side = min(img.shape[:2])
    y0 = (img.shape[0] - side) // 2
    x0 = (img.shape[1] - side) // 2
    chip = img[y0 : y0 + side, x0 : x0 + side]
    chip = cv2.resize(chip, (224, 224), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(chip, cv2.COLOR_GRAY2BGR)
