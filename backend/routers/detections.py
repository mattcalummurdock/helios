from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from helios_common.db import SyncSessionLocal

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("")
async def list_detections():
    return {"message": "Detection endpoints — Phase 4"}


@router.get("/{detection_id}/gradcam")
async def get_detection_gradcam(detection_id: int):
    """Serve stored Grad-CAM PNG for a detection."""
    with SyncSessionLocal() as session:
        row = session.execute(
            text("SELECT gradcam_path FROM detections WHERE id = :id"),
            {"id": detection_id},
        ).fetchone()

    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Grad-CAM not found for detection")

    path = Path(row[0])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Grad-CAM file missing on disk")

    return FileResponse(path, media_type="image/png", filename=f"gradcam_{detection_id}.png")
