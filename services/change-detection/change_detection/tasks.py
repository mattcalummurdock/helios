import logging
from pathlib import Path

import numpy as np
from sqlalchemy import select, text

from helios_common.celery_app import celery_app
from helios_common.config import settings
from helios_common.db import SyncSessionLocal
from helios_common.models import ChangeEvent, ChangeEventType, Detection, Scene
from helios_common.paths import scene_tiles_dir
from helios_common.triton_client import infer_bit

logger = logging.getLogger(__name__)


def _tile_pairs(t1_dir: Path, t2_dir: Path) -> list[tuple[str, str]]:
    pairs = []
    for t2 in sorted(t2_dir.glob("*.tif")):
        t1 = t1_dir / t2.name
        if t1.exists():
            pairs.append((str(t1), str(t2)))
    return pairs


def _detection_centers(session, scene_id: int) -> list[tuple[int, float, float, str]]:
    rows = session.execute(
        text(
            "SELECT id, lat, lon, class FROM detections WHERE scene_id = :sid"
        ),
        {"sid": scene_id},
    ).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _match_detections(
    t1_dets: list[tuple[int, float, float, str]],
    t2_dets: list[tuple[int, float, float, str]],
    max_dist_m: float = 50.0,
) -> tuple[list, list, list]:
    matched_t1 = set()
    matched_t2 = set()
    moved = []

    for i, (id2, lat2, lon2, cls2) in enumerate(t2_dets):
        best_j, best_dist = None, max_dist_m
        for j, (id1, lat1, lon1, cls1) in enumerate(t1_dets):
            if j in matched_t1 or cls1 != cls2:
                continue
            dist = _haversine_m(lat1, lon1, lat2, lon2)
            if dist < best_dist:
                best_dist = dist
                best_j = j
        if best_j is not None:
            matched_t1.add(best_j)
            matched_t2.add(i)
            id1 = t1_dets[best_j][0]
            if best_dist > 5.0:
                moved.append((id1, id2, best_dist))

    appeared = [t2_dets[i] for i in range(len(t2_dets)) if i not in matched_t2]
    disappeared = [t1_dets[j] for j in range(len(t1_dets)) if j not in matched_t1]
    return appeared, disappeared, moved


@celery_app.task(name="change_detection.tasks.detect_changes")
def detect_changes(aoi_id: int, t1_scene_id: int, t2_scene_id: int) -> dict:
    """Run BIT change detection between two scenes and write change_events."""
    t1_dir = scene_tiles_dir(t1_scene_id)
    t2_dir = scene_tiles_dir(t2_scene_id)
    pairs = _tile_pairs(t1_dir, t2_dir)
    change_pixels = 0

    for t1_path, t2_path in pairs:
        try:
            mask = infer_bit(t1_path, t2_path)
            change_pixels += int(np.sum(mask >= settings.bit_change_threshold))
        except Exception as exc:
            logger.exception("BIT inference failed %s %s: %s", t1_path, t2_path, exc)

    events_created = 0
    with SyncSessionLocal() as session:
        t1_dets = _detection_centers(session, t1_scene_id)
        t2_dets = _detection_centers(session, t2_scene_id)
        appeared, disappeared, moved = _match_detections(t1_dets, t2_dets)

        for det in appeared:
            session.add(
                ChangeEvent(
                    aoi_id=aoi_id,
                    event_type=ChangeEventType.APPEARED,
                    detection_id_t2=det[0],
                )
            )
            events_created += 1
        for det in disappeared:
            session.add(
                ChangeEvent(
                    aoi_id=aoi_id,
                    event_type=ChangeEventType.DISAPPEARED,
                    detection_id_t1=det[0],
                )
            )
            events_created += 1
        for id1, id2, dist_m in moved:
            session.add(
                ChangeEvent(
                    aoi_id=aoi_id,
                    event_type=ChangeEventType.MOVED,
                    detection_id_t1=id1,
                    detection_id_t2=id2,
                    distance_moved_m=dist_m,
                )
            )
            events_created += 1

        session.commit()

    logger.info(
        "Change detection aoi=%s t1=%s t2=%s events=%d change_pixels=%d",
        aoi_id,
        t1_scene_id,
        t2_scene_id,
        events_created,
        change_pixels,
    )
    return {
        "aoi_id": aoi_id,
        "t1_scene_id": t1_scene_id,
        "t2_scene_id": t2_scene_id,
        "events_created": events_created,
        "change_pixels": change_pixels,
        "status": "complete",
    }
