import logging

from sqlalchemy import select

from helios_common.celery_app import celery_app
from helios_common.db import SyncSessionLocal
from helios_common.models import Aoi, AoiPriority
from scene_watcher.logging_utils import log_event
from scene_watcher.scene_discovery import discover_scenes_for_aoi

logger = logging.getLogger(__name__)


@celery_app.task(name="scene_watcher.tasks.poll_active_aois")
def poll_active_aois(priority_filter: str = "medium") -> dict:
    """Scene Watcher — poll active AOIs via Copernicus STAC and Planet API."""
    priority_map = {
        "high": [AoiPriority.HIGH],
        "medium": [AoiPriority.MEDIUM, AoiPriority.LOW],
    }
    priorities = priority_map.get(priority_filter, [AoiPriority.MEDIUM, AoiPriority.LOW])

    results = []
    with SyncSessionLocal() as session:
        stmt = select(Aoi).where(
            Aoi.monitoring_active.is_(True),
            Aoi.priority.in_(priorities),
        )
        aois = session.scalars(stmt).all()

        log_event(
            logger,
            "poll_start",
            priority_filter=priority_filter,
            aoi_count=len(aois),
        )

        for aoi in aois:
            result = discover_scenes_for_aoi(session, aoi)
            results.append(result)

    total_discovered = sum(r["discovered"] for r in results)
    log_event(
        logger,
        "poll_finished",
        priority_filter=priority_filter,
        total_discovered=total_discovered,
        aoi_results=results,
    )
    return {
        "priority_filter": priority_filter,
        "aoi_count": len(results),
        "total_discovered": total_discovered,
        "results": results,
    }
