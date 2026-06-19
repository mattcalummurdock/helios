"""Preprocessing pipeline orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path

from geoalchemy2.shape import to_shape

from helios_common.paths import scene_processed_path, scene_raw_dir
from helios_common.models import Aoi, Scene
from preprocessor.steps.atmospheric import apply_atmospheric_correction
from preprocessor.steps.normalize import normalize_bands
from preprocessor.steps.orthorectify import orthorectify
from preprocessor.steps.pansharpen import pansharpen
from preprocessor.steps.tiling import tile_image

logger = logging.getLogger(__name__)


def _aoi_bounds(aoi: Aoi) -> tuple[float, float, float, float]:
    geom = to_shape(aoi.polygon)
    return geom.bounds


def run_preprocessing_pipeline(scene: Scene, aoi: Aoi) -> tuple[Path, list[str]]:
    raw_dir = Path(scene.scene_path or str(scene_raw_dir(scene.id)))
    if not raw_dir.exists():
        raw_dir = scene_raw_dir(scene.id)

    work_dir = raw_dir.parent / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    collection_hint = scene.external_scene_id

    logger.info("Pipeline step 1/5: atmospheric correction")
    atm_dir = apply_atmospheric_correction(raw_dir, scene.sensor_type, collection_hint, work_dir)

    logger.info("Pipeline step 2/5: orthorectification")
    ortho_dir = orthorectify(atm_dir, work_dir, _aoi_bounds(aoi))

    logger.info("Pipeline step 3/5: pansharpening")
    pan_dir = pansharpen(ortho_dir, scene.sensor_type, work_dir)

    logger.info("Pipeline step 4/5: band normalisation")
    processed = scene_processed_path(scene.id)
    normalize_bands(pan_dir, scene.sensor_type, processed)

    logger.info("Pipeline step 5/5: tiling")
    tile_paths = tile_image(processed, scene.id)

    return processed, tile_paths
