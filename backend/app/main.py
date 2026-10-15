"""FastAPI app entry point.

Dev (two processes, hot reload): uvicorn backend.app.main:app --reload  +  npm run dev
Packaged (one process, one port): build the frontend once (npm run build),
then this same command serves the UI too — see run.bat at the repo root.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.errors import register_exception_handlers
from backend.app.jobs import manager
from backend.app.routers import fibers, modes, power, bpm, jobs, fbg, splicing, thermal, devices, coupler, taper, system, gnlse, power_ramp
from backend.app import ws
from backend.app.database import engine, Base
import backend.app.models.device  # noqa: F401 — registers ORM model
import backend.app.models.system  # noqa: F401 — registers ORM model

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    manager.attach_loop(asyncio.get_running_loop())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lampy API",
        description="Backend for the Lampy / fibersim web UI",
        version="0.1.0",
        lifespan=_lifespan,
    )
    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # GZip large numeric payloads (BPM intensity slices, power evolution)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    app.include_router(fibers.router)
    app.include_router(modes.router)
    app.include_router(power.router)
    app.include_router(bpm.router)
    app.include_router(jobs.router)
    app.include_router(fbg.router)
    app.include_router(splicing.router)
    app.include_router(thermal.router)
    app.include_router(coupler.router)
    app.include_router(taper.router)
    app.include_router(devices.router)
    app.include_router(system.router)
    app.include_router(gnlse.router)
    app.include_router(power_ramp.router)
    app.include_router(ws.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Serve the built frontend (npm run build) as a single packaged process.
    # Registered last so it never shadows the API/WebSocket routes above —
    # Starlette matches routes in registration order.
    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
