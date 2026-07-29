"""
Phase 10D.2 — Mission Definition Pipeline tests.

Covers the central contract (Mission Definition / Mission Package), the
replaceable persistence layer (SQLite + in-memory), Planning-Core integration,
fleet inventory, and the REST API contract.

Boundary intent verified here: the pipeline only persists definitions and
orchestrates the existing core/ chain — it never mutates Digital Twin runtime
state and adds no planning algorithms.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.mission_pipeline.models import (
    DefinitionValidationError,
    MissionDefinition,
)
from backend.mission_pipeline.persistence import (
    InMemoryDefinitionStore,
    NotFoundError,
    SQLiteDefinitionStore,
)
from backend.mission_pipeline.planning_core import build_mission_package
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app


def _definition_payload() -> dict:
    return {
        "name": "North Field Spray",
        "field": {
            "name": "North Field",
            "crop_type": "wheat",
            "boundary_points": [[0, 0], [400, 0], [400, 300], [0, 300]],
            "zones": [
                {
                    "zone_id": "z1",
                    "kind": "crop",
                    "label": "Main",
                    "crop_type": "wheat",
                    "boundary_points": [[0, 0], [400, 0], [400, 300]],
                }
            ],
            "obstacles": [
                {"obstacle_id": "o1", "kind": "pole", "label": "Pylon",
                 "points": [[10, 10]]}
            ],
        },
        "operation": {"operation_type": "spray", "num_drones": 3,
                      "flight_altitude_m": 4.0, "planning_mode": "automatic"},
        "environment": {"temperature_c": 24.0, "wind_speed_kmh": 12.0},
        "fleet": [
            {"drone_id": 1, "model": "ORION-Std", "vendor": "ORION",
             "battery_capacity_mah": 16000, "liquid_capacity_l": 10},
            {"drone_id": 2, "model": "ORION-Heavy", "vendor": "ORION",
             "battery_capacity_mah": 22000, "liquid_capacity_l": 20},
        ],
        "products": [
            {"product_id": "herbicide_a", "name": "Herbicide A",
             "rate_l_per_ha": 12.0}
        ],
    }


# ----------------------------------------------------------------------
# Models / contract
# ----------------------------------------------------------------------

def test_definition_roundtrip_preserves_identity_and_fields() -> None:
    definition = MissionDefinition.from_json(_definition_payload())
    restored = MissionDefinition.from_json(definition.to_json())
    assert restored.id == definition.id
    assert restored.name == "North Field Spray"
    assert restored.field.crop_type == "wheat"
    assert len(restored.field.boundary_points) == 4
    assert restored.field.boundary_points[1] == (400.0, 0.0)
    assert len(restored.field.zones) == 1
    assert len(restored.field.obstacles) == 1
    assert len(restored.fleet) == 2
    assert restored.products[0].product_id == "herbicide_a"


def test_definition_requires_name_and_field() -> None:
    with pytest.raises(DefinitionValidationError):
        MissionDefinition.from_json({"field": {"name": "F", "crop_type": "wheat"}})
    with pytest.raises(DefinitionValidationError):
        MissionDefinition.from_json({"name": "no field"})


# ----------------------------------------------------------------------
# Planning Core integration
# ----------------------------------------------------------------------

def test_build_package_from_drawn_polygon() -> None:
    definition = MissionDefinition.from_json(_definition_payload())
    package = build_mission_package(definition).to_json()

    assert package["definition_id"] == definition.id
    assert package["field_geometry"]["is_synthetic"] is False
    assert package["field_geometry"]["area_ha"] == pytest.approx(12.0, abs=0.1)
    # fleet of 2 selected -> 2 planned routes.
    assert len(package["routes"]) == 2
    assert len(package["execution"]["routes_m"]) == 2
    assert package["execution"]["num_drones"] == 2
    assert package["resources"]["mission_duration_min"] > 0
    assert package["recommendation"]["go_no_go"]
    assert package["validation"]["valid"] is True
    # execution package carries geometry for the Digital Twin.
    assert len(package["execution"]["field_polygon_m"]) >= 4


def test_build_package_synthetic_when_no_polygon() -> None:
    payload = _definition_payload()
    payload["field"]["boundary_points"] = []
    payload["field"]["area_ha"] = 20.0
    payload["fleet"] = []
    payload["operation"]["num_drones"] = 4
    definition = MissionDefinition.from_json(payload)
    package = build_mission_package(definition).to_json()

    assert package["field_geometry"]["is_synthetic"] is True
    assert package["field_geometry"]["area_ha"] == pytest.approx(20.0, abs=0.5)
    assert package["execution"]["num_drones"] == 4


# ----------------------------------------------------------------------
# Persistence (replaceable layer)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("store_factory", ["memory", "sqlite"])
def test_definition_persistence_crud(tmp_path, store_factory: str) -> None:
    if store_factory == "memory":
        store = InMemoryDefinitionStore()
    else:
        store = SQLiteDefinitionStore(str(tmp_path / "pipeline.db"))

    definition = MissionDefinition.from_json(_definition_payload())
    store.save_definition(definition)

    loaded = store.get_definition(definition.id)
    assert loaded.name == definition.name
    assert [d.id for d in store.list_definitions()] == [definition.id]

    store.delete_definition(definition.id)
    with pytest.raises(NotFoundError):
        store.get_definition(definition.id)


def test_sqlite_persists_across_connections(tmp_path) -> None:
    db = str(tmp_path / "pipeline.db")
    definition = MissionDefinition.from_json(_definition_payload())
    SQLiteDefinitionStore(db).save_definition(definition)
    # A fresh store (new connection) must see the committed record.
    reopened = SQLiteDefinitionStore(db)
    assert reopened.get_definition(definition.id).name == definition.name


def test_field_persistence_crud() -> None:
    store = InMemoryDefinitionStore()
    record = store.save_field("field_1", {"name": "F", "crop_type": "corn"})
    assert record["id"] == "field_1"
    assert store.get_field("field_1")["crop_type"] == "corn"
    assert len(store.list_fields()) == 1
    store.delete_field("field_1")
    with pytest.raises(NotFoundError):
        store.get_field("field_1")


# ----------------------------------------------------------------------
# REST API contract
# ----------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    runtime = TwinRuntime(num_drones=3, failure_seed=7)
    app = create_app(
        runtime=runtime,
        autostart_mission=False,
        run_loop=False,
        definition_store=InMemoryDefinitionStore(),
    )
    return TestClient(app)


def test_fleet_inventory_endpoint(client: TestClient) -> None:
    resp = client.get("/api/fleet/inventory")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["drone_models"]) >= 1
    assert len(body["products"]) >= 1
    assert "wheat" in body["crop_types"]


def test_mission_crud_and_compute_endpoints(client: TestClient) -> None:
    created = client.post("/api/missions", json=_definition_payload())
    assert created.status_code == 201
    mission_id = created.json()["id"]

    assert client.get("/api/missions").json()["missions"][0]["id"] == mission_id
    assert client.get(f"/api/missions/{mission_id}").status_code == 200

    # compute by stored id
    pkg = client.post(f"/api/missions/{mission_id}/package")
    assert pkg.status_code == 200
    assert pkg.json()["definition_id"] == mission_id
    assert len(pkg.json()["routes"]) == 2

    # compute via inline definition (not persisted)
    inline = client.post("/api/planning/compute", json=_definition_payload())
    assert inline.status_code == 200
    assert len(inline.json()["execution"]["routes_m"]) == 2

    # compute via reference
    ref = client.post("/api/planning/compute", json={"mission_id": mission_id})
    assert ref.status_code == 200
    assert ref.json()["definition_id"] == mission_id

    deleted = client.delete(f"/api/missions/{mission_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/missions/{mission_id}").status_code == 404


def test_update_mission_increments_version(client: TestClient) -> None:
    mission_id = client.post("/api/missions", json=_definition_payload()).json()["id"]
    payload = _definition_payload()
    payload["name"] = "Renamed"
    updated = client.put(f"/api/missions/{mission_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["version"] == 2
    assert updated.json()["id"] == mission_id


def test_field_endpoints(client: TestClient) -> None:
    created = client.post("/api/fields", json={"name": "North", "crop_type": "wheat"})
    assert created.status_code == 201
    field_id = created.json()["id"]
    assert client.get(f"/api/fields/{field_id}").json()["crop_type"] == "wheat"
    assert client.get("/api/fields").json()["fields"][0]["id"] == field_id
    assert client.delete(f"/api/fields/{field_id}").status_code == 200
    assert client.get(f"/api/fields/{field_id}").status_code == 404


def test_bad_definition_returns_400(client: TestClient) -> None:
    assert client.post("/api/missions", json={"field": {}}).status_code == 400
    assert client.post("/api/planning/compute", json={"mission_id": "nope"}).status_code == 404


def test_pipeline_does_not_touch_runtime(client: TestClient) -> None:
    """Design-time endpoints must not change Digital Twin runtime state."""
    before = client.get("/api/twin/state").json()["mission_status"]
    client.post("/api/missions", json=_definition_payload())
    client.post("/api/planning/compute", json=_definition_payload())
    after = client.get("/api/twin/state").json()["mission_status"]
    assert before == after
