"""
Phase 10C.4 — Digital Twin API backend tests.

Covers serialization, REST endpoints, WebSocket stream, intent handling
(intent-only, no decision logic), replay, snapshots, and analytics.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.serializers import serialize_swarm_state
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app


@pytest.fixture()
def runtime() -> TwinRuntime:
    rt = TwinRuntime(num_drones=3, failure_seed=7)
    rt.start_mission()
    for _ in range(6):
        rt.tick()
    return rt


@pytest.fixture()
def client(runtime: TwinRuntime) -> TestClient:
    app = create_app(runtime=runtime, autostart_mission=False, run_loop=False)
    return TestClient(app)


# ----------------------------------------------------------------------
# Serialization
# ----------------------------------------------------------------------

def test_serialize_swarm_state_matches_contract(runtime: TwinRuntime) -> None:
    payload = serialize_swarm_state(runtime._twin.get_swarm_state())
    for key in (
        "swarm_id", "timestamp_ms", "mission_status", "simulation_time_ms",
        "drone_states", "global_health", "active_failures",
        "environment_state", "total_drones", "active_drones",
        "failed_drones", "version",
    ):
        assert key in payload
    assert isinstance(payload["drone_states"], list)
    d = payload["drone_states"][0]
    for key in ("drone_id", "position", "velocity", "battery_pct", "health"):
        assert key in d
    assert set(d["position"]) == {"latitude", "longitude", "altitude_m"}


def test_enums_serialized_as_wire_values(runtime: TwinRuntime) -> None:
    payload = serialize_swarm_state(runtime._twin.get_swarm_state())
    assert payload["mission_status"] in {
        "IDLE", "RUNNING", "PAUSED", "FAILED", "COMPLETED",
    }
    assert payload["global_health"] in {"OK", "WARNING", "CRITICAL"}


# ----------------------------------------------------------------------
# REST endpoints
# ----------------------------------------------------------------------

def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_swarm_state(client: TestClient) -> None:
    r = client.get("/api/twin/state")
    assert r.status_code == 200
    body = r.json()
    assert body["total_drones"] == 3
    assert len(body["drone_states"]) == 3
    # Drones moved through the command path (not stuck at origin).
    assert any(d["position"]["longitude"] != 0.0 for d in body["drone_states"])


def test_drone_state_and_404(client: TestClient) -> None:
    r = client.get("/api/twin/drone/1")
    assert r.status_code == 200
    assert r.json()["drone_id"] == 1
    assert client.get("/api/twin/drone/999").status_code == 404


def test_snapshots(client: TestClient) -> None:
    r = client.get("/api/twin/snapshots")
    assert r.status_code == 200
    snaps = r.json()
    assert len(snaps) >= 1
    sid = snaps[0]["snapshot_id"]
    detail = client.get(f"/api/twin/snapshots/{sid}")
    assert detail.status_code == 200
    assert detail.json()["snapshot_id"] == sid
    assert client.get("/api/twin/snapshots/does-not-exist").status_code == 404


def test_replay(client: TestClient) -> None:
    r = client.post("/api/twin/replay", json={})
    assert r.status_code == 200
    tl = r.json()
    assert "frames" in tl and tl["total_frames"] == len(tl["frames"])


def test_drone_replay(client: TestClient) -> None:
    r = client.get("/api/twin/replay/drone/1")
    assert r.status_code == 200
    assert r.json()["drone_id"] == 1


def test_analytics_only_aggregates_backend_data(client: TestClient) -> None:
    r = client.get("/api/twin/analytics")
    assert r.status_code == 200
    an = r.json()
    assert an["snapshot_count"] >= 1
    assert set(an["alert_frequency"]) == {"INFO", "WARNING", "CRITICAL"}
    assert "battery_trends" in an and "fleet_utilization" in an


def test_mission_geometry(client: TestClient) -> None:
    r = client.get("/api/mission/geometry")
    assert r.status_code == 200
    geo = r.json()
    assert "field_polygon" in geo and len(geo["field_polygon"]) == 4
    assert set(geo["planned_routes"]) == {"1", "2", "3"}


# ----------------------------------------------------------------------
# Intents (intent-only, no decision logic)
# ----------------------------------------------------------------------

def _intent(kind: str) -> dict:
    return {
        "intent_type": kind,
        "payload": {},
        "user_id": "test",
        "timestamp_ms": 0,
    }


def test_intent_lifecycle(client: TestClient) -> None:
    assert client.post("/api/intents", json=_intent("PAUSE_MISSION")).json()["accepted"] is True
    assert client.get("/api/twin/state").json()["mission_status"] == "PAUSED"
    assert client.post("/api/intents", json=_intent("RESUME_MISSION")).json()["accepted"] is True
    assert client.get("/api/twin/state").json()["mission_status"] == "RUNNING"
    assert client.post("/api/intents", json=_intent("STOP_MISSION")).json()["accepted"] is True
    assert client.get("/api/twin/state").json()["mission_status"] == "COMPLETED"


def test_intent_snapshot(client: TestClient) -> None:
    before = len(client.get("/api/twin/snapshots").json())
    r = client.post("/api/intents", json=_intent("REQUEST_SNAPSHOT"))
    assert r.json()["accepted"] is True
    after = len(client.get("/api/twin/snapshots").json())
    assert after == before + 1


def test_unknown_intent_rejected(client: TestClient) -> None:
    r = client.post("/api/intents", json=_intent("DELETE_EVERYTHING"))
    assert r.json()["accepted"] is False


# ----------------------------------------------------------------------
# WebSocket stream
# ----------------------------------------------------------------------

def test_websocket_initial_messages(client: TestClient) -> None:
    with client.websocket_connect("/ws/twin") as ws:
        first = ws.receive_json()
        assert first["type"] == "SWARM_STATE"
        assert "drone_states" in first["payload"]
        second = ws.receive_json()
        assert second["type"] == "MISSION_STATUS"


# ----------------------------------------------------------------------
# Failure propagation
# ----------------------------------------------------------------------

def test_failure_propagates_to_twin() -> None:
    rt = TwinRuntime(num_drones=3, failure_seed=7)
    rt.start_mission()
    rt.inject_failure("link_loss", [2])
    for _ in range(4):
        rt.tick()
    state = rt.get_swarm_payload()
    d2 = next(d for d in state["drone_states"] if d["drone_id"] == 2)
    assert d2["communication_active"] is False
    assert "link_loss" in state["active_failures"]
