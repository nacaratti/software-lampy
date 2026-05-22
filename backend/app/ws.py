"""WebSocket endpoint for streaming job progress and result events."""
from __future__ import annotations
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.jobs import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_socket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    try:
        await manager.subscribe(job_id, queue)
    except KeyError:
        await websocket.send_text(json.dumps({"type": "error", "message": f"job {job_id} not found"}))
        await websocket.close(code=1008)
        return

    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(json.dumps(msg))
            if msg.get("type") in ("result", "error", "cancelled", "expired"):
                # Allow final messages to flush, then close
                await asyncio.sleep(0.05)
                if msg["type"] != "result":
                    break
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("WebSocket error for job %s", job_id)
    finally:
        manager.unsubscribe(job_id, queue)
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
