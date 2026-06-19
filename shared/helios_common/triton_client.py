"""Triton HTTP client helpers for YOLO, MSTAR, and BIT models."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_common.config import settings

logger = logging.getLogger(__name__)

YOLO_CLASSES = ["vehicle", "ship", "aircraft", "helicopter"]
MSTAR_CLASSES = [
    "2S1",
    "BRDM_2",
    "BTR_60",
    "D7",
    "SLICY",
    "T62",
    "ZIL131",
    "ZSU_23_4",
]


@dataclass
class YoloDetection:
    class_name: str
    confidence: float
    lat: float
    lon: float
    heading_degrees: float | None
    bbox_wkt: str
    pixel_box: tuple[float, float, float, float]
    tile_path: str = ""


@dataclass
class MstarResult:
    class_name: str
    confidence: float


def _triton_client():
    import tritonclient.http as httpclient

    url = settings.triton_url
    if not url.startswith("http"):
        url = f"http://{url}"
    return httpclient.InferenceServerClient(url=url)


def _load_tile_rgb(path: str, size: int) -> np.ndarray:
    import cv2

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (size, size), interpolation=cv2.INTER_LINEAR)
    return img.astype(np.float32) / 255.0


def _load_tile_gray(path: str, size: int) -> np.ndarray:
    import cv2

    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(path)
    img = cv2.resize(img, (size, size), interpolation=cv2.INTER_LINEAR)
    return img.astype(np.float32) / 255.0


def _pixel_to_lonlat(
    cx: float,
    cy: float,
    tile_path: str,
    img_size: int,
) -> tuple[float, float]:
    import rasterio

    with rasterio.open(tile_path) as src:
        scale_x = src.width / img_size
        scale_y = src.height / img_size
        px = cx * scale_x
        py = cy * scale_y
        lon, lat = src.transform * (px, py)
    return lat, lon


def _obb_corners(cx: float, cy: float, w: float, h: float, angle: float, img_size: int) -> list[tuple[float, float]]:
    cx_p, cy_p = cx * img_size, cy * img_size
    w_p, h_p = w * img_size, h * img_size
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    corners = []
    for dx, dy in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
        x = dx * w_p
        y = dy * h_p
        rx = cx_p + x * cos_a - y * sin_a
        ry = cy_p + x * sin_a + y * cos_a
        corners.append((rx / img_size, ry / img_size))
    return corners


def _corners_to_wkt(corners_norm: list[tuple[float, float]], tile_path: str, img_size: int) -> str:
    coords = []
    for cx, cy in corners_norm:
        lat, lon = _pixel_to_lonlat(cx, cy, tile_path, img_size)
        coords.append(f"{lon} {lat}")
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return f"POLYGON(({', '.join(coords)}))"


def _parse_yolo_output(output: np.ndarray, conf_min: float) -> list[tuple]:
    """Parse YOLO OBB output tensor into (cx,cy,w,h,angle,conf,cls) rows."""
    arr = np.squeeze(output)
    if arr.ndim == 2 and arr.shape[0] in (7, 8, 11, 12):
        arr = arr.T
    if arr.ndim != 2:
        return []
    rows = []
    for row in arr:
        if row.shape[0] < 7:
            continue
        cx, cy, w, h, angle = row[0], row[1], row[2], row[3], row[4]
        if row.shape[0] == 7:
            conf, cls_id = float(row[5]), int(row[6])
        else:
            cls_scores = row[5:-1] if row.shape[0] > 7 else row[5:9]
            cls_id = int(np.argmax(cls_scores))
            conf = float(row[-1]) if row.shape[0] > 7 else float(np.max(cls_scores))
        if conf < conf_min:
            continue
        rows.append((cx, cy, w, h, angle, conf, cls_id))
    return rows


def nms_detections(detections: list[YoloDetection], iou_threshold: float) -> list[YoloDetection]:
    if len(detections) <= 1:
        return detections

    def iou(a: YoloDetection, b: YoloDetection) -> float:
        ax1, ay1, ax2, ay2 = a.pixel_box
        bx1, by1, bx2, by2 = b.pixel_box
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list[YoloDetection] = []
    for det in sorted_dets:
        if all(iou(det, k) < iou_threshold for k in kept):
            kept.append(det)
    return kept


def infer_yolo(tile_path: str, img_size: int = 640) -> list[YoloDetection]:
    import tritonclient.http as httpclient

    t0 = time.perf_counter()
    client = _triton_client()
    model = settings.triton_yolo_model

    img = _load_tile_rgb(tile_path, img_size)
    chw = np.transpose(img, (2, 0, 1)).astype(np.float32)

    inputs = [httpclient.InferInput("images", chw.shape, "FP32")]
    inputs[0].set_data_from_numpy(chw)
    outputs = [httpclient.InferRequestedOutput("output0")]

    result = client.infer(model_name=model, inputs=inputs, outputs=outputs)
    raw = result.as_numpy("output0")
    rows = _parse_yolo_output(raw, settings.yolo_confidence_min)

    detections: list[YoloDetection] = []
    for cx, cy, w, h, angle, conf, cls_id in rows:
        cls_name = YOLO_CLASSES[cls_id] if cls_id < len(YOLO_CLASSES) else "vehicle"
        lat, lon = _pixel_to_lonlat(cx, cy, tile_path, img_size)
        corners = _obb_corners(cx, cy, w, h, angle, img_size)
        wkt = _corners_to_wkt(corners, tile_path, img_size)
        px_corners = [(c[0] * img_size, c[1] * img_size) for c in corners]
        xs = [p[0] for p in px_corners]
        ys = [p[1] for p in px_corners]
        detections.append(
            YoloDetection(
                class_name=cls_name,
                confidence=conf,
                lat=lat,
                lon=lon,
                heading_degrees=math.degrees(angle) % 360,
                bbox_wkt=wkt,
                pixel_box=(min(xs), min(ys), max(xs), max(ys)),
                tile_path=tile_path,
            )
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("infer_yolo tile=%s dets=%d %.1fms", tile_path, len(detections), elapsed_ms)
    return detections


def infer_mstar(tile_path: str, img_size: int = 224) -> MstarResult:
    import tritonclient.http as httpclient

    t0 = time.perf_counter()
    client = _triton_client()
    model = settings.triton_mstar_model

    gray = _load_tile_gray(tile_path, img_size)
    chw = gray[np.newaxis, ...].astype(np.float32)

    inputs = [httpclient.InferInput("input", chw.shape, "FP32")]
    inputs[0].set_data_from_numpy(chw)
    outputs = [httpclient.InferRequestedOutput("output")]

    result = client.infer(model_name=model, inputs=inputs, outputs=outputs)
    logits = result.as_numpy("output").squeeze()
    probs = _softmax(logits)
    cls_id = int(np.argmax(probs))
    conf = float(probs[cls_id])
    cls_name = MSTAR_CLASSES[cls_id] if cls_id < len(MSTAR_CLASSES) else f"class_{cls_id}"

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("infer_mstar tile=%s class=%s conf=%.3f %.1fms", tile_path, cls_name, conf, elapsed_ms)
    return MstarResult(class_name=cls_name, confidence=conf)


def infer_bit(t1_path: str, t2_path: str, img_size: int = 256) -> np.ndarray:
    import tritonclient.http as httpclient

    t0 = time.perf_counter()
    client = _triton_client()
    model = settings.triton_bit_model

    t1 = np.transpose(_load_tile_rgb(t1_path, img_size), (2, 0, 1)).astype(np.float32)
    t2 = np.transpose(_load_tile_rgb(t2_path, img_size), (2, 0, 1)).astype(np.float32)

    inputs = [
        httpclient.InferInput("t1", t1.shape, "FP32"),
        httpclient.InferInput("t2", t2.shape, "FP32"),
    ]
    inputs[0].set_data_from_numpy(t1)
    inputs[1].set_data_from_numpy(t2)
    outputs = [httpclient.InferRequestedOutput("change_mask")]

    result = client.infer(model_name=model, inputs=inputs, outputs=outputs)
    mask = result.as_numpy("change_mask").squeeze()

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("infer_bit t1=%s t2=%s %.1fms", t1_path, t2_path, elapsed_ms)
    return mask


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()
