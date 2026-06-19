import logging

from helios_common.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="alert_service.tasks.scan_alerts")
def scan_alerts() -> dict:
    """Placeholder alert scan task — Phase 4 implementation."""
    logger.info("Alert scan running (stub)")
    return {"status": "stub", "alerts_fired": 0}
