"""
Phase 10D.6 — Mission Review & Deployment tests.

Covers the operational gateway between planning and execution: the review
payload (Mission Package + deployment record), the operator checklist gate, the
single deployment responsibility (transfer the package to the Digital Twin),
Mission Package immutability after deployment, and the Mission Control handoff.

Boundary intent: Mission Review never plans, optimizes, allocates, schedules or
routes; it reaches the runtime only through the Digital Twin deployment
interface, transfers the package unchanged, and never starts execution.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi.testclient import TestClient

from backend.mission_pipeline import deployment as deployment_module
from backend.mission_pipeline.deployment import (
    DeploymentError,
    DeploymentRecord,
    DeploymentState,
    deploy_mission,
    new_record,
)
from backend.mission_pipeline.persistence import (
    InMemoryDefinitionStore,
    NotFoundError,
    SQLiteDefinitionStore,
)
from backend.serializers import JSONObject
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app


def _mission_payload() -> dict:
    return {
        "name": "Review mission",
        "field": {
            "name": "North Vineyard",
            "crop_type": "grapes",
            "boundary_points": [[0, 0], [400, 0], [400, 300], [0, 300]],
        },
        "operation": {"operation_type": "spray", "num_drones": 2},
        "products": [
            {"product_id": "herbicide_a", "name": "Herbicide A", "rate_l_per_ha": 12.0}
        ],
        "fleet": [
            {
                "drone_id": 1,
                "model": "ORION-Std",
                "vendor": "ORION",
                "battery_capacity_mah": 16000.0,
                "liquid_capacity_l": 10.0,
                "working_width_m": 5.0,
            },
            {
                "drone_id": 2,
                "model": "DJI-Agras-T40",
                "vendor": "DJI",
                "battery_capacity_mah": 30000.0,
                "liquid_capacity_l": 40.0,
                "working_width_m": 9.0,
            },
        ],
    }


@pytest.fixture()
def client() -> TestClient:
    app = create_app(
        runtime=TwinRuntime(num_drones=3, failure_seed=7),
        autostart_mission=False,
        run_loop=False,
        definition_store=InMemoryDefinitionStore(),
    )
    return TestClient(app)


def _create_mission(client: TestClient) -> str:
    created = client.post("/api/missions", json=_mission_payload())
    assert created.status_code == 201
    mission_id = created.json()["id"]
    assert isinstance(mission_id, str)
    return mission_id


def _confirm_all(client: TestClient, mission_id: str) -> JSONObject:
    review = client.get(f"/api/missions/{mission_id}/review").json()
    confirmations = {i["item_id"]: True for i in review["deployment"]["checklist"]}
    resp = client.put(
        f"/api/missions/{mission_id}/checklist",
        json={"confirmations": confirmations},
    )
    assert resp.status_code == 200
    return resp.json()


# ----------------------------------------------------------------------
# Deployment record: state machine + checklist gate (pure unit level)
# ----------------------------------------------------------------------

def test_state_progresses_draft_to_ready_to_approved() -> None:
    record = new_record("m1")
    assert record.state == DeploymentState.DRAFT
    assert not record.checklist_complete

    record.confirm({"weather_verified": True})
    assert record.state == DeploymentState.READY_FOR_REVIEW

    record.confirm({i.item_id: True for i in record.checklist})
    assert record.state == DeploymentState.APPROVED
    assert record.checklist_complete
    assert not record.is_locked


def test_checklist_roundtrips_through_json() -> None:
    record = new_record("m1")
    record.confirm({"area_inspected": True})
    restored = DeploymentRecord.from_json(record.to_json())
    assert restored.state == DeploymentState.READY_FOR_REVIEW
    confirmed = {i.item_id for i in restored.checklist if i.confirmed}
    assert confirmed == {"area_inspected"}


def test_deploy_requires_complete_checklist() -> None:
    record = new_record("m1")
    record.confirm({"weather_verified": True})

    class _Gateway:
        def deploy_mission_package(self, package: JSONObject) -> JSONObject:
            raise AssertionError("gateway must not be reached")

    with pytest.raises(DeploymentError, match="checklist incomplete"):
        deploy_mission(record, {"definition_id": "m1"}, _Gateway())


def test_deploy_transfers_package_unchanged_and_locks() -> None:
    record = new_record("m1")
    record.confirm({i.item_id: True for i in record.checklist})
    package: JSONObject = {
        "definition_id": "m1",
        "routes": [{"drone_id": 1}, {"drone_id": 2}],
    }
    received: list[JSONObject] = []

    class _Gateway:
        def deploy_mission_package(self, pkg: JSONObject) -> JSONObject:
            received.append(pkg)
            return {"accepted": True, "deployment_id": "deploy_test"}

    record, receipt = deploy_mission(record, package, _Gateway())

    assert received == [package]
    assert receipt["deployment_id"] == "deploy_test"
    assert record.state == DeploymentState.DEPLOYED
    assert record.is_locked
    assert record.package == package

    # A deployed record refuses further changes and re-deployment.
    with pytest.raises(DeploymentError):
        record.confirm({"weather_verified": False})
    with pytest.raises(DeploymentError, match="already deployed"):
        deploy_mission(record, package, _Gateway())


def test_review_and_deployment_modules_import_no_runtime_modules() -> None:
    """Mission Review reaches the Twin only through the injected gateway."""
    forbidden = (
        "hive",
        "hal",
        "px4",
        "mavlink",
        "ros2",
        "simulation",
        "digital_twin",
        "backend.twin_runtime",
        "backend.twin_server",
    )
    root = pathlib.Path(deployment_module.__file__).parent
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text())
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        for module in modules:
            head = module.split(".")[0]
            assert not any(
                module.startswith(bad) or head == bad for bad in forbidden
            ), f"{path.name} imports forbidden runtime module '{module}'"


# ----------------------------------------------------------------------
# REST: review payload, checklist gating, deployment
# ----------------------------------------------------------------------

def test_review_returns_package_and_draft_deployment(client: TestClient) -> None:
    mission_id = _create_mission(client)
    resp = client.get(f"/api/missions/{mission_id}/review")
    assert resp.status_code == 200
    body = resp.json()

    assert body["mission"]["id"] == mission_id
    assert body["deployment_available"] is True
    # Everything the review screen shows comes from the Planning Core package.
    package = body["package"]
    for key in (
        "routes",
        "resources",
        "timeline",
        "risks",
        "recommendation",
        "validation",
        "execution",
    ):
        assert key in package

    record = body["deployment"]
    assert record["state"] == DeploymentState.DRAFT.value
    assert record["checklist_complete"] is False
    assert record["locked"] is False
    assert len(record["checklist"]) == len(deployment_module.DEFAULT_CHECKLIST)


def test_review_of_unknown_mission_is_404(client: TestClient) -> None:
    assert client.get("/api/missions/nope/review").status_code == 404


def test_deploy_rejected_until_checklist_complete(client: TestClient) -> None:
    mission_id = _create_mission(client)
    resp = client.post(f"/api/missions/{mission_id}/deploy")
    assert resp.status_code == 409
    assert "checklist incomplete" in resp.json()["detail"].lower()

    twin = client.get("/api/twin/deployment").json()
    assert twin["deployed"] is False


def test_checklist_updates_persist_and_approve(client: TestClient) -> None:
    mission_id = _create_mission(client)
    partial = client.put(
        f"/api/missions/{mission_id}/checklist",
        json={"confirmations": {"weather_verified": True}},
    ).json()
    assert partial["state"] == DeploymentState.READY_FOR_REVIEW.value

    approved = _confirm_all(client, mission_id)
    assert approved["state"] == DeploymentState.APPROVED.value
    assert approved["checklist_complete"] is True

    reread = client.get(f"/api/missions/{mission_id}/review").json()["deployment"]
    assert reread["state"] == DeploymentState.APPROVED.value


def test_checklist_rejects_malformed_body(client: TestClient) -> None:
    mission_id = _create_mission(client)
    resp = client.put(
        f"/api/missions/{mission_id}/checklist", json={"confirmations": "yes"}
    )
    assert resp.status_code == 400


def test_deploy_transfers_package_to_twin_without_starting_execution(
    client: TestClient,
) -> None:
    mission_id = _create_mission(client)
    _confirm_all(client, mission_id)

    before = client.get("/api/twin/state").json()
    resp = client.post(f"/api/missions/{mission_id}/deploy")
    assert resp.status_code == 200
    body = resp.json()

    assert body["deployment"]["state"] == DeploymentState.DEPLOYED.value
    assert body["deployment"]["locked"] is True
    assert body["receipt"]["accepted"] is True

    after = client.get("/api/twin/state").json()
    assert after["mission_status"] == before["mission_status"]
    assert client.get("/api/mission/status").json()["progress"] == 0.0

    # Mission Control handoff: the Twin holds exactly the deployed package.
    twin = client.get("/api/twin/deployment").json()
    assert twin["deployed"] is True
    assert twin["deployment_id"] == body["deployment"]["deployment_id"]
    assert twin["package"] == body["deployment"]["package"]
    assert twin["package"]["definition_id"] == mission_id


def test_deployed_mission_definition_is_immutable(client: TestClient) -> None:
    mission_id = _create_mission(client)
    _confirm_all(client, mission_id)
    assert client.post(f"/api/missions/{mission_id}/deploy").status_code == 200

    edited = _mission_payload()
    edited["name"] = "Renamed after deployment"
    update = client.put(f"/api/missions/{mission_id}", json=edited)
    assert update.status_code == 409
    assert "locked" in update.json()["detail"]

    assert client.delete(f"/api/missions/{mission_id}").status_code == 409
    assert (
        client.put(
            f"/api/missions/{mission_id}/checklist",
            json={"confirmations": {"weather_verified": False}},
        ).status_code
        == 409
    )
    assert client.post(f"/api/missions/{mission_id}/deploy").status_code == 409

    stored = client.get(f"/api/missions/{mission_id}").json()
    assert stored["name"] == "Review mission"


def test_deployed_package_is_frozen_not_recomputed(client: TestClient) -> None:
    mission_id = _create_mission(client)
    _confirm_all(client, mission_id)
    deployed = client.post(f"/api/missions/{mission_id}/deploy").json()
    locked = deployed["deployment"]["package"]

    # Every later package read returns the exact deployed artifact, so the
    # runtime and the operator can never diverge.
    again = client.post(f"/api/missions/{mission_id}/package").json()
    assert again == locked
    assert again["generated_ms"] == locked["generated_ms"]

    review = client.get(f"/api/missions/{mission_id}/review").json()
    assert review["package"] == locked

    compute = client.post(
        "/api/planning/compute", json={"mission_id": mission_id}
    ).json()
    assert compute == locked


def test_deployment_record_survives_reload(tmp_path) -> None:
    db = str(tmp_path / "pipeline.db")
    store = SQLiteDefinitionStore(db)
    record = new_record("m1")
    record.confirm({"weather_verified": True, "area_inspected": True})
    store.save_deployment(record)

    reopened = SQLiteDefinitionStore(db)
    restored = reopened.get_deployment("m1")
    assert restored.state == DeploymentState.READY_FOR_REVIEW
    assert {i.item_id for i in restored.checklist if i.confirmed} == {
        "weather_verified",
        "area_inspected",
    }

    reopened.delete_deployment("m1")
    with pytest.raises(NotFoundError):
        reopened.get_deployment("m1")


def test_review_and_preview_do_not_mutate_runtime_state(client: TestClient) -> None:
    """Reading the review payload (which drives the preview) is inert."""
    mission_id = _create_mission(client)
    before = client.get("/api/twin/state").json()

    client.get(f"/api/missions/{mission_id}/review")
    client.get(f"/api/missions/{mission_id}/review")
    client.put(
        f"/api/missions/{mission_id}/checklist",
        json={"confirmations": {"weather_verified": True}},
    )

    after = client.get("/api/twin/state").json()
    assert before["mission_status"] == after["mission_status"]
    assert before["mission_id"] == after["mission_id"]
    assert client.get("/api/twin/deployment").json()["deployed"] is False


def test_deployment_unavailable_without_gateway(tmp_path) -> None:
    """The design-time API still works when no Digital Twin is attached."""
    from fastapi import FastAPI

    from backend.mission_pipeline.api import create_pipeline_router
    from backend.mission_pipeline.field_images import create_default_image_store

    app = FastAPI()
    app.include_router(
        create_pipeline_router(
            InMemoryDefinitionStore(),
            create_default_image_store(str(tmp_path / "images")),
        )
    )
    standalone = TestClient(app)
    mission_id = _create_mission(standalone)
    _confirm_all(standalone, mission_id)

    review = standalone.get(f"/api/missions/{mission_id}/review").json()
    assert review["deployment_available"] is False
    assert standalone.post(f"/api/missions/{mission_id}/deploy").status_code == 503
