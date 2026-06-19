import logging

from helios_common.celery_app import celery_app
from helios_common.db import SyncSessionLocal
from helios_common.models import Aoi, Scene

logger = logging.getLogger(__name__)


@celery_app.task(
    name="preprocessor.tasks.preprocess_scene",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def preprocess_scene(self, scene_id: int) -> dict:
    """Run full preprocessing pipeline and enqueue inference."""
    with SyncSessionLocal() as session:
        scene = session.get(Scene, scene_id)
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")

        aoi = session.get(Aoi, scene.aoi_id)
        if not aoi:
            raise ValueError(f"AOI {scene.aoi_id} not found for scene {scene_id}")

        logger.info("Starting preprocessing for scene_id=%s sensor=%s", scene_id, scene.sensor_type)
        from preprocessor.pipeline import run_preprocessing_pipeline

        processed_path, tile_paths = run_preprocessing_pipeline(scene, aoi)

        scene.scene_path = str(processed_path)
        scene.processed = True
        session.commit()

    celery_app.send_task(
        "inference_service.tasks.run_inference",
        args=[scene_id, tile_paths],
        queue="inference",
    )
    logger.info(
        "Preprocessing complete scene_id=%s tiles=%d inference enqueued",
        scene_id,
        len(tile_paths),
    )
    return {
        "scene_id": scene_id,
        "processed_path": str(processed_path),
        "tile_count": len(tile_paths),
        "status": "complete",
    }
