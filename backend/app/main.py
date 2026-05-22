"""FastAPI app entry point.

Run with:
    uvicorn backend.app.main:app --reload
"""
from __future__ import annotations
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.app.config import settings
from backend.app.jobs import manager
from backend.app.routers import fibers, modes, power, bpm, jobs, fbg, splicing, thermal, devices
from backend.app import ws
from backend.app.database import engine, Base
import backend.app.models.device  # noqa: F401 — registers ORM model


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lampy API",
        description="Backend for the Lampy / fibersim web UI",
        version="0.1.0",
    )

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
    app.include_router(devices.router)
    app.include_router(ws.router)

    @app.on_event("startup")
    async def attach_loop() -> None:
        Base.metadata.create_all(bind=engine)
        manager.attach_loop(asyncio.get_running_loop())

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
