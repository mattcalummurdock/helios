"""Per-AOI scene discovery orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from helios_common.clients.copernicus import CopernicusClient
from helios_common.clients.planet import PlanetClient
from helios_common.config import settings
from helios_common.models import Aoi, Scene
from helios_common.paths import scene_raw_dir
from scene_watcher.download import download_copernicus_scene, download_planet_scene
from scene_watcher.logging_utils import log_event

logger = logging.getLogger(__name__)


def _aoi_geojson(aoi: Aoi) -> dict:
    geom = to_shape(aoi.polygon)
    return {"type": "Polygon", "coordinates": [list(geom.exterior.coords)]}


def _known_external_ids(session: Session) -> set[str]:
    rows = session.scalars(select(Scene.external_scene_id)).all()
    return set(rows)


def _enqueue_preprocessing(scene_id: int) -> None:
    celery_app.send_task(
        "preprocessor.tasks.preprocess_scene",
        args=[scene_id],
        queue="preprocessing",
    )


def _register_and_download_copernicus(
    session: Session,
    aoi: Aoi,
    candidate,
) -> int | None:
    scene = Scene(
        aoi_id=aoi.id,
        satellite_source="copernicus",
        external_scene_id=candidate.external_id,
        sensor_type=candidate.sensor_type,
        acquisition_timestamp=candidate.acquisition_timestamp,
        cloud_cover_pct=candidate.cloud_cover_pct,
        scene_path=str(scene_raw_dir(0)),
        processed=False,
    )
    session.add(scene)
    session.flush()

    scene.scene_path = str(scene_raw_dir(scene.id))
    download_copernicus_scene(scene.id, candidate)
    session.commit()

    _enqueue_preprocessing(scene.id)
    log_event(
        logger,
        "scene_discovered",
        source="copernicus",
        aoi_id=aoi.id,
        scene_id=scene.id,
        external_id=candidate.external_id,
        sensor_type=candidate.sensor_type,
        status="preprocessing_enqueued",
    )
    return scene.id


def _register_and_download_planet(
    session: Session,
    aoi: Aoi,
    candidate,
) -> int | None:
    scene = Scene(
        aoi_id=aoi.id,
        satellite_source="planet",
        external_scene_id=candidate.external_id,
        sensor_type="planet",
        acquisition_timestamp=candidate.acquisition_timestamp,
        cloud_cover_pct=candidate.cloud_cover_pct,
        scene_path=str(scene_raw_dir(0)),
        processed=False,
    )
    session.add(scene)
    session.flush()

    scene.scene_path = str(scene_raw_dir(scene.id))
    download_planet_scene(scene.id, candidate.external_id)
    session.commit()

    _enqueue_preprocessing(scene.id)
    log_event(
        logger,
        "scene_discovered",
        source="planet",
        aoi_id=aoi.id,
        scene_id=scene.id,
        external_id=candidate.external_id,
        sensor_type="planet",
        status="preprocessing_enqueued",
    )
    return scene.id


def discover_scenes_for_aoi(session: Session, aoi: Aoi) -> dict:
    """Poll Copernicus + Planet for new scenes covering an AOI."""
    known = _known_external_ids(session)
    geojson = _aoi_geojson(aoi)
    discovered = 0
    errors: list[str] = []

    try:
        cop_client = CopernicusClient()
        candidates = cop_client.search_scenes(geojson, aoi.last_pass_at, known)
        for candidate in candidates[:3]:
            try:
                _register_and_download_copernicus(session, aoi, candidate)
                discovered += 1
                known.add(candidate.external_id)
            except Exception as exc:
                session.rollback()
                errors.append(f"copernicus:{candidate.external_id}:{exc}")
                log_event(
                    logger,
                    "scene_download_error",
                    source="copernicus",
                    aoi_id=aoi.id,
                    external_id=candidate.external_id,
                    error=str(exc),
                )
    except Exception as exc:
        errors.append(f"copernicus_search:{exc}")
        log_event(logger, "poll_error", source="copernicus", aoi_id=aoi.id, error=str(exc))

    if settings.planet_api_key:
        try:
            planet_client = PlanetClient()
            planet_candidates = planet_client.search_scenes(geojson, aoi.last_pass_at, known)
            for candidate in planet_candidates[:1]:
                try:
                    _register_and_download_planet(session, aoi, candidate)
                    discovered += 1
                    known.add(candidate.external_id)
                except Exception as exc:
                    session.rollback()
                    errors.append(f"planet:{candidate.external_id}:{exc}")
                    log_event(
                        logger,
                        "scene_download_error",
                        source="planet",
                        aoi_id=aoi.id,
                        external_id=candidate.external_id,
                        error=str(exc),
                    )
        except Exception as exc:
            errors.append(f"planet_search:{exc}")
            log_event(logger, "poll_error", source="planet", aoi_id=aoi.id, error=str(exc))
    else:
        log_event(logger, "poll_skip", source="planet", aoi_id=aoi.id, reason="no_api_key")

    if not errors:
        aoi.last_pass_at = datetime.now(timezone.utc)
        session.commit()
        log_event(
            logger,
            "poll_complete",
            aoi_id=aoi.id,
            aoi_name=aoi.name,
            discovered=discovered,
            last_pass_at=aoi.last_pass_at.isoformat(),
        )
    else:
        session.rollback()
        log_event(
            logger,
            "poll_partial_failure",
            aoi_id=aoi.id,
            aoi_name=aoi.name,
            discovered=discovered,
            errors=errors,
        )

    return {"aoi_id": aoi.id, "discovered": discovered, "errors": errors}
