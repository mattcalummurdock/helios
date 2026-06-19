from fastapi import APIRouter

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("")
async def list_changes():
    return {"message": "Change event endpoints — Phase 4"}
