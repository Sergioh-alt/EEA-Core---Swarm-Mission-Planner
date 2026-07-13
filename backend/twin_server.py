"""
Phase 10C.4 — Digital Twin API Server (FastAPI + WebSocket).

Thin, READ-ONLY transport that serializes and streams the Digital Twin
(Single Source of Truth) to the ORIÓN UI.

Endpoints (mirror orion-ui/src/contracts/api.ts exactly):
    GET  /api/health
    GET  /api/twin/state
    GET  /api/twin/drone/{drone_id}
    GET  /api/twin/snapshots
    GET  /api/twin/snapshots/{snapshot_id}
    POST /api/twin/replay
    GET  /api/twin/replay/drone/{drone_id}
    POST /api/intents
    GET  /api/twin/analytics
    GET  /api/mission/geometry
    WS   /ws/twin

The server NEVER exposes write access to the Digital Twin. The only
write path from the UI is intent submission, which maps to operator
mission lifecycle (START/PAUSE/STOP/REPLAY) — no decision-making.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.serializers import JSONObject, JSONValue
from backend.twin_runtime import TwinRuntime

logger = logging.getLogger("eea.backend.twin_server")

# Broadcast rate: 2 Hz (within the 1–2 Hz spec).
DEFAULT_TICK_INTERVAL_S = 0.5


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts server messages."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: JSONObject) -> None:
        async with self._lock:
            clients = list(self._clients)
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)


def _server_message(msg_type: str, payload: JSONValue) -> JSONObject:
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp_ms": int(time.time() * 1000),
    }


async def _read_json_object(request: Request) -> JSONObject:
    """Parse a JSON request body, returning {} for empty/invalid input."""
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def create_app(
    runtime: Optional[TwinRuntime] = None,
    tick_interval_s: float = DEFAULT_TICK_INTERVAL_S,
    autostart_mission: bool = True,
    run_loop: bool = True,
) -> FastAPI:
    """Build the FastAPI app. `run_loop=False` is used for tests."""
    runtime = runtime or TwinRuntime()
    manager = ConnectionManager()

    async def _tick_loop() -> None:
        if autostart_mission:
            runtime.start_mission()
        while True:
            result = await asyncio.to_thread(runtime.tick)
            await manager.broadcast(_server_message("SWARM_STATE", result["swarm"]))
            await manager.broadcast(_server_message("MISSION_STATUS", result["mission"]))
            for alert in result["alerts"]:
                await manager.broadcast(_server_message("ALERT", alert))
            await asyncio.sleep(tick_interval_s)

    @contextlib.asynccontextmanager
    async def _lifespan(_: FastAPI):
        task = asyncio.create_task(_tick_loop()) if run_loop else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="ORIÓN Digital Twin API", version="10C.4", lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.runtime = runtime
    app.state.manager = manager

    # ------------------------------------------------------------------
    # REST — read-only
    # ------------------------------------------------------------------

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "connections": manager.count})

    @app.get("/api/twin/state")
    async def swarm_state() -> JSONResponse:
        return JSONResponse(runtime.get_swarm_payload())

    @app.get("/api/twin/drone/{drone_id}")
    async def drone_state(drone_id: int) -> JSONResponse:
        payload = runtime.get_drone_payload(drone_id)
        if payload is None:
            return JSONResponse({"detail": "drone not found"}, status_code=404)
        return JSONResponse(payload)

    @app.get("/api/twin/snapshots")
    async def snapshots() -> JSONResponse:
        return JSONResponse(runtime.list_snapshots_payload())

    @app.get("/api/twin/snapshots/{snapshot_id}")
    async def snapshot(snapshot_id: str) -> JSONResponse:
        payload = runtime.get_snapshot_payload(snapshot_id)
        if payload is None:
            return JSONResponse({"detail": "snapshot not found"}, status_code=404)
        return JSONResponse(payload)

    @app.post("/api/twin/replay")
    async def replay(request: Request) -> JSONResponse:
        body = await _read_json_object(request)
        start = body.get("start_version")
        end = body.get("end_version")
        return JSONResponse(runtime.replay_timeline_payload(
            start_version=start if isinstance(start, int) else None,
            end_version=end if isinstance(end, int) else None,
        ))

    @app.get("/api/twin/replay/drone/{drone_id}")
    async def replay_drone(drone_id: int) -> JSONResponse:
        return JSONResponse(runtime.replay_drone_payload(drone_id))

    @app.get("/api/twin/analytics")
    async def analytics() -> JSONResponse:
        return JSONResponse(runtime.analytics())

    @app.get("/api/mission/geometry")
    async def mission_geometry() -> JSONResponse:
        return JSONResponse(runtime.mission_geometry())

    @app.get("/api/mission/status")
    async def mission_status() -> JSONResponse:
        return JSONResponse(runtime.get_mission_payload())

    @app.get("/api/alerts")
    async def alerts() -> JSONResponse:
        return JSONResponse(runtime.get_alerts())

    # ------------------------------------------------------------------
    # Intents — the ONLY UI write path (operator lifecycle, no planning)
    # ------------------------------------------------------------------

    @app.post("/api/intents")
    async def submit_intent(request: Request) -> JSONResponse:
        intent = await _read_json_object(request)
        raw_type = intent.get("intent_type", "")
        intent_type = raw_type if isinstance(raw_type, str) else ""
        accepted = False
        message = "unknown intent"

        if intent_type == "START_MISSION":
            accepted = runtime.start_mission()
            message = "mission started" if accepted else "already running"
        elif intent_type == "PAUSE_MISSION":
            accepted = runtime.pause_mission()
            message = "mission paused" if accepted else "not running"
        elif intent_type == "RESUME_MISSION":
            accepted = runtime.resume_mission()
            message = "mission resumed" if accepted else "not paused"
        elif intent_type == "STOP_MISSION":
            accepted = runtime.stop_mission()
            message = "mission stopped" if accepted else "not active"
        elif intent_type == "REQUEST_SNAPSHOT":
            snap_id = runtime.request_snapshot()
            accepted = True
            message = f"snapshot {snap_id} created"
        elif intent_type in ("START_REPLAY", "STOP_REPLAY"):
            # Replay is a read-only client-side operation over REST data.
            accepted = True
            message = "replay acknowledged"

        result = {
            "accepted": accepted,
            "intent_type": intent_type,
            "message": message,
            "timestamp_ms": int(time.time() * 1000),
        }
        # Reflect any lifecycle change to all clients immediately.
        await manager.broadcast(
            _server_message("MISSION_STATUS", runtime.get_mission_payload())
        )
        return JSONResponse(result)

    # ------------------------------------------------------------------
    # WebSocket — real-time state stream
    # ------------------------------------------------------------------

    @app.websocket("/ws/twin")
    async def ws_twin(ws: WebSocket) -> None:
        await manager.connect(ws)
        try:
            # Send an immediate snapshot so the UI paints without waiting.
            await ws.send_json(_server_message("SWARM_STATE", runtime.get_swarm_payload()))
            await ws.send_json(_server_message("MISSION_STATUS", runtime.get_mission_payload()))
            await ws.send_json(_server_message("CONNECTION_STATUS", {"latency_ms": 0}))
            while True:
                # Client → server messages (SUBSCRIBE / SET_UPDATE_RATE) are
                # accepted but require no action in this read-only stream.
                await ws.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(ws)
        except Exception:
            await manager.disconnect(ws)

    return app


def _autostart_from_env() -> bool:
    return os.environ.get("TWIN_AUTOSTART", "1").lower() not in ("0", "false", "no")


def _tick_interval_from_env() -> float:
    try:
        return float(os.environ.get("TWIN_TICK_INTERVAL_S", DEFAULT_TICK_INTERVAL_S))
    except ValueError:
        return DEFAULT_TICK_INTERVAL_S


app = create_app(
    autostart_mission=_autostart_from_env(),
    tick_interval_s=_tick_interval_from_env(),
)
