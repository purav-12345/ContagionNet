"""
Layer 5 — WebSocket endpoint /ws/contagion.

Runs the requested algorithm and broadcasts the state ONE STEP AT A TIME, so the
frontend animates the contagion spreading wave by wave in real time.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.simulation_runner import run_simulation_steps
from api.state import APP_STATE

logger = logging.getLogger("api.ws")
router = APIRouter()


@router.websocket("/ws/contagion")
async def contagion_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        params = json.loads(raw)

        bank_id = params["bank_id"]
        shock_magnitude = float(params["shock_magnitude"])
        algorithm = params.get("algorithm", "debtrank")
        step_delay = float(params.get("step_delay_ms", 800)) / 1000.0

        if not APP_STATE.ready:
            await websocket.send_json({"error": "Network not ready", "simulation_complete": True})
            return
        if bank_id not in APP_STATE.index_by_id:
            await websocket.send_json(
                {"error": f"Unknown bank_id: {bank_id}", "simulation_complete": True}
            )
            return

        # Compute the full normalized step list, then stream it step by step.
        steps = run_simulation_steps(APP_STATE, bank_id, shock_magnitude, algorithm)

        for step in steps:
            await websocket.send_json(step)
            if step.get("simulation_complete"):
                break
            await asyncio.sleep(step_delay)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.exception("WebSocket simulation error")
        try:
            await websocket.send_json({"error": str(exc), "simulation_complete": True})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
