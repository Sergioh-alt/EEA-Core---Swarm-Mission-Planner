"""
Phase 10D.5 — Fleet Configuration tests.

Covers the additive fleet-configuration contract (per-drone equipment, sensors,
camera/sprayer/spreader selection, and per-tank product assignment), its
(de)serialization and backward compatibility, the enriched read-only fleet
inventory, mission persistence of a heterogeneous configured fleet, and the
Planning-Core boundary (configuration never mutates runtime state and the
enriched fields do not disturb geometry/planning).

Boundary intent: Fleet Configuration only *selects* and *configures* available
assets and constructs a MissionDefinition. It performs no allocation, resource
balancing, optimization or scheduling, and never touches Digital Twin runtime.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.mission_pipeline.fleet_inventory import get_fleet_inventory
from backend.mission_pipeline.models import MissionDefinition
from backend.mission_pipeline.persistence import InMemoryDefinitionStore
from backend.mission_pipeline.planning_core import build_mission_package
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app


def _configured_fleet() -> list[dict]:
    return [
        {
            "drone_id": 1,
            "model": "ORION-Std",
            "vendor": "ORION",
            "battery_capacity_mah": 16000.0,
            "liquid_capacity_l": 10.0,
            "working_width_m": 5.0,
            "status": "available",
            "payload_capacity_kg": 10.0,
            "estimated_flight_time_min": 18.0,
            "supported_operations": ["spray", "fertilization"],
            "sensors": ["RTK-GPS", "Flow Meter"],
            "equipment": ["Standard Sprayer"],
            "camera_package": "RGB",
            "sprayer_config": "Fine Mist",
            "granular_spreader": None,
            "tanks": [
                {
                    "tank_id": "A",
                    "label": "Tank A",
                    "capacity_l": 10.0,
                    "product_id": "herbicide_a",
                    "product_name": "Herbicide A",
                }
            ],
        },
        {
            "drone_id": 2,
            "model": "DJI-Agras-T40",
            "vendor": "DJI",
            "battery_capacity_mah": 30000.0,
            "liquid_capacity_l": 40.0,
            "working_width_m": 9.0,
            "status": "available",
            "payload_capacity_kg": 40.0,
            "estimated_flight_time_min": 18.0,
            "supported_operations": ["spray", "seeding"],
            "sensors": ["RTK-GPS", "Dual FPV"],
            "equipment": ["Spreading System 2.0"],
            "camera_package": "FPV",
            "sprayer_config": "Standard",
            "granular_spreader": "Spreading System 2.0",
            "tanks": [
                {
                    "tank_id": "A",
                    "label": "Tank A",
                    "capacity_l": 20.0,
                    "product_id": "water",
                    "product_name": "Water (calibration)",
                },
                {
                    "tank_id": "B",
                    "label": "Tank B",
                    "capacity_l": 20.0,
                    "product_id": "fertilizer_c",
                    "product_name": "Liquid Fertilizer C",
                },
            ],
        },
    ]


def _mission_payload() -> dict:
    return {
        "name": "Fleet cfg mission",
        "field": {
            "name": "North Vineyard",
            "crop_type": "grapes",
            "boundary_points": [[0, 0], [400, 0], [400, 300], [0, 300]],
        },
        "operation": {"operation_type": "spray", "num_drones": 2},
        "products": [
            {"product_id": "herbicide_a", "name": "Herbicide A", "rate_l_per_ha": 12.0}
        ],
        "fleet": _configured_fleet(),
    }


# ----------------------------------------------------------------------
# Inventory: enriched read-only catalog
# ----------------------------------------------------------------------

def test_inventory_exposes_enriched_heterogeneous_catalog() -> None:
    inv = get_fleet_inventory()
    models = {m["model"]: m for m in inv["drone_models"]}
    # Heterogeneous vendors incl. the third-party example XAG-P100.
    assert {"ORION-Std", "ORION-Heavy", "DJI-Agras-T40", "XAG-P100"} <= set(models)
    assert models["XAG-P100"]["vendor"] == "XAG"
    std = models["ORION-Std"]
    for key in (
        "status",
        "payload_capacity_kg",
        "estimated_flight_time_min",
        "tanks",
        "supported_operations",
        "sensors",
        "equipment",
        "camera_packages",
        "sprayer_configs",
    ):
        assert key in std
    assert all("capacity_l" in t for t in std["tanks"])


# ----------------------------------------------------------------------
# Contract: configured fleet roundtrip + backward compatibility
# ----------------------------------------------------------------------

def test_configured_fleet_roundtrip_preserves_all_fields() -> None:
    definition = MissionDefinition.from_json(_mission_payload())
    restored = MissionDefinition.from_json(definition.to_json())

    assert len(restored.fleet) == 2
    orion, dji = restored.fleet
    assert orion.equipment == ["Standard Sprayer"]
    assert orion.camera_package == "RGB"
    assert orion.sprayer_config == "Fine Mist"
    assert orion.sensors == ["RTK-GPS", "Flow Meter"]
    assert orion.tanks[0].product_id == "herbicide_a"

    assert dji.granular_spreader == "Spreading System 2.0"
    assert [t.product_name for t in dji.tanks] == [
        "Water (calibration)",
        "Liquid Fertilizer C",
    ]
    assert dji.payload_capacity_kg == pytest.approx(40.0)


def test_legacy_fleet_without_config_still_parses() -> None:
    # A 10D.4-style fleet item (no equipment/tanks) deserializes with defaults.
    definition = MissionDefinition.from_json(
        {
            "name": "Legacy",
            "field": {"name": "F", "crop_type": "corn"},
            "fleet": [
                {
                    "drone_id": 1,
                    "model": "ORION-Std",
                    "vendor": "ORION",
                    "battery_capacity_mah": 16000.0,
                    "liquid_capacity_l": 10.0,
                }
            ],
        }
    )
    item = definition.fleet[0]
    assert item.equipment == []
    assert item.sensors == []
    assert item.tanks == []
    assert item.camera_package is None
    assert item.status is None


# ----------------------------------------------------------------------
# Persistence + Planning-Core boundary
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


def test_configured_fleet_persists_via_rest(client: TestClient) -> None:
    created = client.post("/api/missions", json=_mission_payload())
    assert created.status_code == 201
    mission_id = created.json()["id"]

    fetched = client.get(f"/api/missions/{mission_id}").json()
    fleet = fetched["fleet"]
    assert len(fleet) == 2
    assert fleet[1]["tanks"][1]["product_id"] == "fertilizer_c"
    assert fleet[0]["camera_package"] == "RGB"


def test_configured_fleet_does_not_break_planning_core() -> None:
    definition = MissionDefinition.from_json(_mission_payload())
    package = build_mission_package(definition).to_json()
    assert package["field_geometry"]["is_synthetic"] is False
    # num_drones follows the two selected drones.
    assert package["execution"]["num_drones"] == 2
    # Unknown crop stays a non-blocking warning (no contradiction with GO).
    assert package["validation"]["valid"] is True


def test_fleet_configuration_does_not_touch_runtime_state(client: TestClient) -> None:
    before = client.get("/api/twin/state").json()
    created = client.post("/api/missions", json=_mission_payload())
    mission_id = created.json()["id"]
    client.post("/api/planning/compute", json={"mission_id": mission_id})
    after = client.get("/api/twin/state").json()
    assert before["mission_status"] == after["mission_status"]
    assert before["mission_id"] == after["mission_id"]
