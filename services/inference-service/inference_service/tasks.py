import logging
import time
from pathlib import Path

import cv2
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from helios_common.celery_app import celery_app
from helios_common.config import settings
from helios_common.db import SyncSessionLocal
from helios_common.gradcam import save_gradcam_png
from helios_common.models import Detection, Scene, SensorType
from helios_common.paths import scene_tiles_dir
from helios_common.triton_client import (
    MstarResult,
    YoloDetection,
    infer_mstar,
    infer_yolo,
    nms_detections,
)

logger = logging.getLogger(__name__)

OPTICAL_SENSORS = {SensorType.SENTINEL_2.value, SensorType.PLANET.value, "sentinel-2", "planet"}
SAR_SENSORS = {SensorType.SENTINEL_1.value, "sentinel-1"}


def _detection_dir(detection_id: int) -> Path:
    return Path(settings.detections_dir) / str(detection_id)


def _save_crop(tile_path: str, det: YoloDetection, out_path: Path) -> None:
    img = cv2.imread(tile_path)
    if img is None:
        return
    h, w = img.shape[:2]
    x1 = max(0, int(det.pixel_box[0] * w / 640))
    y1 = max(0, int(det.pixel_box[1] * h / 640))
    x2 = min(w, int(det.pixel_box[2] * w / 640))
    y2 = min(h, int(det.pixel_box[3] * h / 640))
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        crop = img
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), crop)


def _insert_yolo_detections(
    session,
    scene: Scene,
    detections: list[YoloDetection],
) -> list[int]:
    ids: list[int] = []
    for det in detections:
        row = Detection(
            scene_id=scene.id,
            aoi_id=scene.aoi_id,
            class_=det.class_name,
            confidence=det.confidence,
            lat=det.lat,
            lon=det.lon,
            heading_degrees=det.heading_degrees,
            bbox_polygon=WKTElement(det.bbox_wkt, srid=4326),
        )
        session.add(row)
        session.flush()
        det_dir = _detection_dir(row.id)
        crop_path = det_dir / "crop.png"
        gradcam_path = det_dir / "gradcam.png"
        if det.tile_path:
            _save_crop(det.tile_path, det, crop_path)
        else:
            crop_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            save_gradcam_png(crop_path, gradcam_path)
            row.gradcam_path = str(gradcam_path)
        except Exception as exc:
            logger.warning("Grad-CAM failed detection_id=%s: %s", row.id, exc)
        row.detection_image_path = str(crop_path)
        ids.append(row.id)
    return ids


def _insert_mstar_detection(session, scene: Scene, tile_path: str, result: MstarResult) -> int | None:
    if result.confidence < settings.mstar_confidence_min:
        return None
    import rasterio

    with rasterio.open(tile_path) as src:
        lon, lat = src.transform * (src.width / 2, src.height / 2)
    row = Detection(
        scene_id=scene.id,
        aoi_id=scene.aoi_id,
        class_=result.class_name,
        confidence=result.confidence,
        lat=lat,
        lon=lon,
        bbox_polygon=WKTElement(f"POINT({lon} {lat})", srid=4326),
    )
    session.add(row)
    session.flush()
    return row.id


def _find_prior_scene(session, scene: Scene) -> Scene | None:
    stmt = (
        select(Scene)
        .where(
            Scene.aoi_id == scene.aoi_id,
            Scene.processed.is_(True),
            Scene.id != scene.id,
            Scene.acquisition_timestamp < scene.acquisition_timestamp,
        )
        .order_by(Scene.acquisition_timestamp.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _collect_tiles(scene_id: int, tile_paths: list[str] | None) -> list[str]:
    if tile_paths:
        return tile_paths
    tiles_dir = scene_tiles_dir(scene_id)
    if not tiles_dir.exists():
        return []
    return sorted(str(p) for p in tiles_dir.glob("*.tif"))


@celery_app.task(name="inference_service.tasks.run_inference")
def run_inference(scene_id: int, tile_paths: list[str] | None = None) -> dict:
    """Run Triton inference on preprocessed tiles and write detections to PostGIS."""
    t_start = time.perf_counter()
    tile_paths = _collect_tiles(scene_id, tile_paths)
    detection_count = 0
    prior_scene_id: int | None = None

    with SyncSessionLocal() as session:
        scene = session.get(Scene, scene_id)
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")

        sensor = scene.sensor_type
        all_yolo: list[YoloDetection] = []
        tile_timings: list[float] = []

        for tile_path in tile_paths:
            t_tile = time.perf_counter()
            try:
                if sensor in OPTICAL_SENSORS:
                    dets = infer_yolo(tile_path)
                    all_yolo.extend(dets)
                elif sensor in SAR_SENSORS:
                    result = infer_mstar(tile_path)
                    if _insert_mstar_detection(session, scene, tile_path, result):
                        detection_count += 1
                else:
                    logger.warning("Unknown sensor_type=%s, defaulting to YOLO", sensor)
                    all_yolo.extend(infer_yolo(tile_path))
            except Exception as exc:
                logger.exception("Inference failed tile=%s: %s", tile_path, exc)
            tile_ms = (time.perf_counter() - t_tile) * 1000
            tile_timings.append(tile_ms)
            logger.info("Tile inference %.1fms tile=%s", tile_ms, tile_path)

        if all_yolo:
            merged = nms_detections(all_yolo, settings.nms_iou_threshold)
            ids = _insert_yolo_detections(session, scene, merged)
            detection_count += len(ids)

        prior = _find_prior_scene(session, scene)
        if prior:
            prior_scene_id = prior.id

        session.commit()

    if prior_scene_id is not None:
        celery_app.send_task(
            "change_detection.tasks.detect_changes",
            args=[scene.aoi_id, prior_scene_id, scene_id],
            queue="change_detection",
        )

    total_ms = (time.perf_counter() - t_start) * 1000
    avg_tile_ms = sum(tile_timings) / len(tile_timings) if tile_timings else 0
    logger.info(
        "Inference complete scene_id=%s detections=%d avg_tile_ms=%.1f total_ms=%.1f",
        scene_id,
        detection_count,
        avg_tile_ms,
        total_ms,
    )
    return {
        "scene_id": scene_id,
        "tile_count": len(tile_paths),
        "detection_count": detection_count,
        "avg_tile_ms": avg_tile_ms,
        "prior_scene_id": prior_scene_id,
        "status": "complete",
    }
