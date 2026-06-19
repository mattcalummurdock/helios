from fastapi import APIRouter

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("")
async def list_scenes():
    return {"message": "Scene endpoints — Phase 4"}
