from fastapi import APIRouter

router = APIRouter(prefix="/aois", tags=["aois"])


@router.get("")
async def list_aois():
    return {"message": "AOI endpoints — Phase 4"}
