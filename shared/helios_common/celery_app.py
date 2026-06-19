import logging
import os

from celery import Celery
from celery.schedules import crontab

from helios_common.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery("helios", broker=settings.redis_url, backend=settings.redis_url)

_default_imports = (
    "scene_watcher.tasks",
    "preprocessor.tasks",
    "inference_service.tasks",
    "change_detection.tasks",
    "alert_service.tasks",
)
_imports = os.getenv("CELERY_IMPORTS")
_task_imports = tuple(i.strip() for i in _imports.split(",") if i.strip()) if _imports else _default_imports

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_queues={
        "scene_watch": {"exchange": "scene_watch", "routing_key": "scene_watch"},
        "preprocessing": {"exchange": "preprocessing", "routing_key": "preprocessing"},
        "inference": {"exchange": "inference", "routing_key": "inference"},
        "change_detection": {"exchange": "change_detection", "routing_key": "change_detection"},
    },
    task_routes={
        "scene_watcher.tasks.poll_active_aois": {"queue": "scene_watch"},
        "preprocessor.tasks.preprocess_scene": {"queue": "preprocessing"},
        "inference_service.tasks.run_inference": {"queue": "inference"},
        "change_detection.tasks.detect_changes": {"queue": "change_detection"},
        "alert_service.tasks.scan_alerts": {"queue": "default"},
    },
    beat_schedule={
        "poll-active-aois-high": {
            "task": "scene_watcher.tasks.poll_active_aois",
            "schedule": crontab(minute="*/30"),
            "kwargs": {"priority_filter": "high"},
        },
        "poll-active-aois-medium": {
            "task": "scene_watcher.tasks.poll_active_aois",
            "schedule": crontab(minute=0, hour="*/2"),
            "kwargs": {"priority_filter": "medium"},
        },
        "scan-alerts": {
            "task": "alert_service.tasks.scan_alerts",
            "schedule": crontab(minute="*/5"),
        },
    },
    imports=_task_imports,
)

logger.info("Celery app configured with broker %s", settings.redis_url)
