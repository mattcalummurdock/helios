import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from helios_common.db import async_engine  # noqa: E402
from routers import aois, alerts, changes, detections, export, scenes, ws  # noqa: E402

app = FastAPI(title="Helios API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aois.router)
app.include_router(detections.router)
app.include_router(changes.router)
app.include_router(alerts.router)
app.include_router(scenes.router)
app.include_router(export.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    db_status = "disconnected"
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as exc:
        return {"status": "degraded", "db": db_status, "error": str(exc)}

    return {"status": "ok", "db": db_status, "phase": 1}


@app.get("/")
async def root():
    return {"service": "helios-api", "phase": 1}
