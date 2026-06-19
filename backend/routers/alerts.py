from fastapi import APIRouter

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts():
    return {"message": "Alert endpoints — Phase 4"}
