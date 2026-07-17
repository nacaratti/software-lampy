"""Shared API error handling and admission control.

Error contract (uniform across all routers):
- 422: solver rejected the input (physically or numerically invalid) —
  body is {"detail": "<ExceptionName>: <message>"} with no traceback.
- 503: server saturated with heavy synchronous computations.
- 500: unexpected failure — generic message to the client, full traceback
  in the server log only.
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.app.config import settings

logger = logging.getLogger(__name__)


def solver_error(exc: Exception) -> HTTPException:
    """Map a solver failure to a clean, traceback-free 422."""
    return HTTPException(status_code=422, detail=f"{type(exc).__name__}: {exc}")


def run_solver(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a solver callable, translating failures into a clean 422.

    HTTPExceptions raised inside (e.g. explicit validation) pass through
    untouched instead of being masked as solver errors.
    """
    try:
        return fn(*args, **kwargs)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Solver call failed: %s", getattr(fn, "__name__", repr(fn)))
        raise solver_error(exc) from exc


def register_exception_handlers(app: FastAPI) -> None:
    """Catch anything a router forgot to handle; never leak internals."""

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AdmissionControl:
    """Bounds concurrency of heavy synchronous solver endpoints.

    Sync endpoints run on Starlette's threadpool; without a cap a burst of
    expensive requests (2D eigenmodes, thermal cavity) can exhaust it. Async
    jobs (ASE/BPM) have their own semaphore in JobManager.
    """

    def __init__(self, max_concurrent: int, acquire_timeout_s: float = 30.0):
        self._sem = threading.Semaphore(max_concurrent)
        self._timeout = acquire_timeout_s

    @contextmanager
    def slot(self, name: str) -> Iterator[None]:
        if not self._sem.acquire(timeout=self._timeout):
            raise HTTPException(
                status_code=503,
                detail=f"Server busy: too many concurrent {name} computations; try again shortly.",
            )
        try:
            yield
        finally:
            self._sem.release()


heavy_solvers = AdmissionControl(settings.max_concurrent_sync_solvers)
