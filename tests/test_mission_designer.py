"""
Phase 10D.4 — Mission Designer tests.

Covers the additive Mission Definition contract extensions captured by the
Mission Designer (mission information, operational preferences, product
application details), their (de)serialization and backward compatibility,
mission CRUD over REST, and Planning-Core integration from a stored mission.

Boundary intent: the Mission Designer only collects design-time parameters and
constructs a MissionDefinition. It performs no planning, routing, optimization,
allocation or scheduling, and never mutates Digital Twin runtime state.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.mission_pipeline.models import (
    FieldSpec,
    MissionDefinition,
    OperationParams,
    ProductSelection,
)
from backend.mission_pipeline.persistence import InMemoryDefinitionStore
from backend.mission_pipeline.planning_core import build_mission_package
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app


def _field_payload() -> dict:
    return {
        "name": "North Vineyard",
        "crop_type": "grapes",
        "meters_per_pixel": 1.0,
        "boundary_points": [[0, 0], [400, 0], [400, 300], [0, 300]],
        "zones": [
            {
                "zone_id": "z1",
                "kind": "treatment",
                "label": "Block A",
                "boundary_points": [[10, 10], [100, 10], [100, 100]],
                "enabled": True,
            }
        ],
        "obstacles": [],
    }


def _mission_payload() -> dict:
    return {
        "name": "Spring spray pass",
        "description": "First treatment of the season",
        "field_id": "field_123",
        "priority": "high",
        "scheduled_date": "2026-04-01",
        "notes": "avoid midday wind",
        "field": _field_payload(),
        "operation": {
            "operation_type": "spraying",
            "num_drones": 2,
            "flight_altitude_m": 12.0,
            "planning_mode": "assisted",
            "nominal_speed_ms": 6.5,
            "overlap_pct": 20.0,
            "safety_margin_m": 3.0,
            "coverage_direction": "north_south",
            "route_preference": "time",
        },
        "products": [
            {
                "product_id": "herbicide_a",
                "name": "Herbicide A",
                "rate_l_per_ha": 12.0,
                "tank": "Tank 1",
                "concentration_pct": 2.5,
                "dilution": "1:100",
                "safety_notes": "PPE required",
            }
        ],
        "fleet": [
            {
                "drone_id": 1,
                "model": "ORION-Std",
                "vendor": "ORION",
                "battery_capacity_mah": 16000.0,
                "liquid_capacity_l": 10.0,
                "working_width_m": 5.0,
            }
        ],
    }


# ----------------------------------------------------------------------
# Contract: additive fields roundtrip
# ----------------------------------------------------------------------

def test_mission_definition_roundtrip_preserves_designer_fields() -> None:
    definition = MissionDefinition.from_json(_mission_payload())
    restored = MissionDefinition.from_json(definition.to_json())

    assert restored.field_id == "field_123"
    assert restored.priority == "high"
    assert restored.scheduled_date == "2026-04-01"
    assert restored.notes == "avoid midday wind"

    op = restored.operation
    assert op.operation_type == "spraying"
    assert op.nominal_speed_ms == pytest.approx(6.5)
    assert op.overlap_pct == pytest.approx(20.0)
    assert op.safety_margin_m == pytest.approx(3.0)
    assert op.coverage_direction == "north_south"
    assert op.route_preference == "time"

    assert len(restored.products) == 1
    product = restored.products[0]
    assert product.tank == "Tank 1"
    assert product.concentration_pct == pytest.approx(2.5)
    assert product.dilution == "1:100"
    assert product.safety_notes == "PPE required"

    assert restored.field.zones[0].enabled is True


def test_mission_definition_backward_compatible_defaults() -> None:
    # A minimal 10D.2-style mission (no designer fields) still parses.
    definition = MissionDefinition.from_json(
        {"name": "Legacy", "field": {"name": "F", "crop_type": "corn"}}
    )
    assert definition.field_id == ""
    assert definition.priority == "normal"
    assert definition.scheduled_date == ""
    assert definition.notes == ""
    assert definition.operation.coverage_direction == "auto"
    assert definition.operation.route_preference == "balanced"
    assert definition.operation.nominal_speed_ms is None


def test_operation_and_product_defaults() -> None:
    op = OperationParams()
    assert op.coverage_direction == "auto"
    assert op.route_preference == "balanced"
    product = ProductSelection(product_id="water", name="Water")
    assert product.tank is None
    assert product.safety_notes == ""


# ----------------------------------------------------------------------
# REST: mission CRUD carries the designer fields
# ----------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    app = create_app(
        runtime=TwinRuntime(num_drones=3, failure_seed=7),
        autostart_mission=False,
        run_loop=False,
        definition_store=InMemoryDefinitionStore(),
    )
    return TestClient(app)


def test_mission_crud_roundtrip(client: TestClient) -> None:
    created = client.post("/api/missions", json=_mission_payload())
    assert created.status_code == 201
    body = created.json()
    mission_id = body["id"]
    assert body["priority"] == "high"
    assert body["operation"]["coverage_direction"] == "north_south"
    assert body["products"][0]["tank"] == "Tank 1"

    fetched = client.get(f"/api/missions/{mission_id}")
    assert fetched.status_code == 200
    assert fetched.json()["notes"] == "avoid midday wind"

    listed = client.get("/api/missions")
    assert listed.status_code == 200
    assert any(m["id"] == mission_id for m in listed.json()["missions"])

    updated_payload = _mission_payload()
    updated_payload["priority"] = "urgent"
    updated = client.put(f"/api/missions/{mission_id}", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["priority"] == "urgent"
    assert updated.json()["version"] == 2

    deleted = client.delete(f"/api/missions/{mission_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/missions/{mission_id}").status_code == 404


# ----------------------------------------------------------------------
# Planning-Core integration from a stored designer mission
# ----------------------------------------------------------------------

def test_planning_compute_from_stored_mission(client: TestClient) -> None:
    created = client.post("/api/missions", json=_mission_payload())
    mission_id = created.json()["id"]

    computed = client.post("/api/planning/compute", json={"mission_id": mission_id})
    assert computed.status_code == 200
    package = computed.json()
    assert package["definition_id"] == mission_id
    assert package["field_geometry"]["is_synthetic"] is False
    assert package["field_geometry"]["area_ha"] == pytest.approx(12.0, abs=0.1)
    assert len(package["routes"]) >= 1
    assert package["execution"]["operation_type"] == "spraying"


def test_designer_fields_do_not_break_planning_core() -> None:
    """The additive preferences must not disturb the Planning-Core geometry."""
    definition = MissionDefinition.from_json(_mission_payload())
    package = build_mission_package(definition).to_json()
    assert package["field_geometry"]["is_synthetic"] is False
    # num_drones follows the selected fleet (1 here), not the requested 2.
    assert package["execution"]["num_drones"] == 1


def test_planning_compute_does_not_touch_runtime_state(client: TestClient) -> None:
    before = client.get("/api/twin/state").json()
    created = client.post("/api/missions", json=_mission_payload())
    client.post(
        "/api/planning/compute", json={"mission_id": created.json()["id"]}
    )
    after = client.get("/api/twin/state").json()
    assert before["mission_status"] == after["mission_status"]
    assert before["mission_id"] == after["mission_id"]
