from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from helios_common.paths import resolve_detection_asset

from deps import get_db, require_auth
from services.queries import fetch_detections_geojson

router = APIRouter(prefix="/detections", tags=["detections"])


def _serve_detection_asset(
    stored_path: str | None,
    detection_id: int,
    filename: str,
    label: str,
) -> FileResponse:
    path = resolve_detection_asset(stored_path, detection_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail=f"{label} file missing on disk")
    return FileResponse(path, media_type="image/png", filename=f"{filename.replace('.png', '')}_{detection_id}.png")


@router.get("")
async def list_detections(
    bbox: str | None = Query(None),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    classes: list[str] | None = Query(None),
    confidence_min: float | None = Query(None),
    aoi_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    return await fetch_detections_geojson(
        session,
        bbox=bbox,
        time_start=time_start,
        time_end=time_end,
        classes=classes,
        confidence_min=confidence_min,
        aoi_id=aoi_id,
    )


@router.get("/{detection_id}/crop")
async def get_detection_crop(
    detection_id: int,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        text("SELECT detection_image_path FROM detections WHERE id = :id"),
        {"id": detection_id},
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Detection not found")
    return _serve_detection_asset(row[0], detection_id, "crop.png", "Crop")


@router.get("/{detection_id}/gradcam")
async def get_detection_gradcam(
    detection_id: int,
    session: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        text("SELECT gradcam_path FROM detections WHERE id = :id"),
        {"id": detection_id},
    )
    row = result.first()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Grad-CAM not found for detection")
    return _serve_detection_asset(row[0], detection_id, "gradcam.png", "Grad-CAM")
