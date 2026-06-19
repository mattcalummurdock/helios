from fastapi import APIRouter

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.get("")
async def websocket_info():
    return {"message": "WebSocket endpoint — Phase 4"}
