"""
Phase 10D.7 — Mission Library & Scheduler tests.

Covers saved reusable missions (templates), template duplication, schedule
persistence with recurrence and several occurrences per day, enable/disable,
Mission Package integrity, execution preparation / Digital Twin handoff, the
separation of execution history from templates, and runtime isolation.

Boundary intent: the library and scheduler persist and retrieve the existing
Mission Definition / Mission Package contract and the operator's explicit
scheduling intent. They never plan, optimize, allocate, resolve conflicts or
own runtime state, and they reach the Twin only through the injected gateway.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.mission_pipeline import library as library_module
from backend.mission_pipeline.execution import (
    ExecutionConflict,
    dispatch_due_schedules,
    prepare_execution,
    resolve_package,
)
from backend.mission_pipeline.library import (
    EntryStatus,
    ExecutionStatus,
    ExecutionTrigger,
    LibraryEntry,
    Recurrence,
    ScheduleEntry,
    ScheduleError,
    apply_runtime_state,
    execution_from_package,
    next_occurrence,
    occurrences,
    validate_schedule,
)
from backend.mission_pipeline.persistence import (
    InMemoryDefinitionStore,
    NotFoundError,
    SQLiteDefinitionStore,
)
from backend.serializers import JSONObject
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app

MINUTE_MS = 60_000
DAY_MS = 24 * 60 * MINUTE_MS


def _mission_payload() -> JSONObject:
    return {
        "name": "Morning Spray",
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
    return created.json()["id"]


def _save_entry(client: TestClient, name: str = "Morning Spray") -> JSONObject:
    mission_id = _create_mission(client)
    resp = client.post("/api/library", json={"mission_id": mission_id, "name": name})
    assert resp.status_code == 201
    return resp.json()


def _at(day: date, clock: str) -> int:
    hour, minute = (int(part) for part in clock.split(":"))
    return int(datetime.combine(day, datetime.min.time()).timestamp() * 1000) + (
        hour * 60 + minute
    ) * MINUTE_MS


class _StubGateway:
    """Minimal Digital Twin stand-in recording exactly what it received."""

    def __init__(self, status: str = "IDLE") -> None:
        self.status = status
        self.deployed: list[JSONObject] = []
        self.starts = 0

    def deploy_mission_package(self, package: JSONObject) -> JSONObject:
        self.deployed.append(package)
        return {"accepted": True, "deployment_id": "deploy_stub"}

    def start_mission(self) -> bool:
        self.starts += 1
        self.status = "RUNNING"
        return True

    def get_mission_payload(self) -> JSONObject:
        return {"status": self.status, "progress": 0.0, "events": []}


# ----------------------------------------------------------------------
# Library entries
# ----------------------------------------------------------------------

def test_saved_mission_stores_definition_and_planning_package(
    client: TestClient,
) -> None:
    entry = _save_entry(client)
    assert entry["template"] is True
    assert entry["status"] == EntryStatus.READY.value
    assert entry["definition"]["name"] == "Morning Spray"

    package = entry["package"]
    for key in ("routes", "resources", "risks", "recommendation", "validation"):
        assert key in package
    assert entry["package_stale"] is False

    summary = entry["summary"]
    assert summary["field_name"] == "North Vineyard"
    assert summary["operation_type"] == "spray"
    assert summary["products"] == ["Herbicide A"]
    assert summary["route_count"] == len(package["routes"])
    assert summary["go_no_go"] == package["recommendation"]["go_no_go"]


def test_library_listing_and_metadata_update(client: TestClient) -> None:
    entry = _save_entry(client)
    listed = client.get("/api/library").json()["entries"]
    assert [e["entry_id"] for e in listed] == [entry["entry_id"]]

    updated = client.put(
        f"/api/library/{entry['entry_id']}",
        json={"name": "Morning Spray v2", "status": EntryStatus.ARCHIVED.value},
    ).json()
    assert updated["name"] == "Morning Spray v2"
    assert updated["status"] == EntryStatus.ARCHIVED.value
    # Metadata edits never touch the stored contract.
    assert updated["definition"] == entry["definition"]
    assert updated["package"] == entry["package"]


def test_library_save_requires_existing_mission(client: TestClient) -> None:
    assert client.post("/api/library", json={}).status_code == 400
    assert client.post("/api/library", json={"mission_id": "nope"}).status_code == 404
    assert client.get("/api/library/nope").status_code == 404
    assert client.delete("/api/library/nope").status_code == 404


def test_saved_mission_survives_reload(tmp_path) -> None:
    db = str(tmp_path / "pipeline.db")
    store = SQLiteDefinitionStore(db)
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray", "field": {"name": "North Vineyard"}},
        package={"definition_id": "m1", "routes": [{"drone_id": 1}]},
        package_definition_version=1,
    )
    store.save_library_entry(entry)

    restored = SQLiteDefinitionStore(db).get_library_entry(entry.entry_id)
    assert restored.name == "Morning Spray"
    assert restored.package == entry.package
    assert restored.template is True

    SQLiteDefinitionStore(db).delete_library_entry(entry.entry_id)
    with pytest.raises(NotFoundError):
        SQLiteDefinitionStore(db).get_library_entry(entry.entry_id)


# ----------------------------------------------------------------------
# Reuse: duplication and package integrity
# ----------------------------------------------------------------------

def test_duplicate_creates_new_definition_without_touching_template(
    client: TestClient,
) -> None:
    entry = _save_entry(client)
    resp = client.post(
        f"/api/library/{entry['entry_id']}/duplicate", json={"name": "Evening Spray"}
    )
    assert resp.status_code == 201
    copy = resp.json()["mission"]

    assert copy["id"] != entry["definition"]["id"]
    assert copy["name"] == "Evening Spray"
    assert copy["version"] == 1
    assert copy["field"]["name"] == entry["definition"]["field"]["name"]
    assert len(copy["fleet"]) == len(entry["definition"]["fleet"])

    # The copy is editable and its edits never reach the saved mission.
    edited = _mission_payload()
    edited["name"] = "Evening Spray edited"
    edited["operation"] = {"operation_type": "fertilization", "num_drones": 2}
    assert client.put(f"/api/missions/{copy['id']}", json=edited).status_code == 200

    unchanged = client.get(f"/api/library/{entry['entry_id']}").json()
    assert unchanged["definition"] == entry["definition"]
    assert unchanged["package"] == entry["package"]
    assert unchanged["summary"]["operation_type"] == "spray"


def test_replanning_a_copy_produces_a_new_package(client: TestClient) -> None:
    entry = _save_entry(client)
    copy = client.post(f"/api/library/{entry['entry_id']}/duplicate", json={}).json()[
        "mission"
    ]
    package = client.post(f"/api/missions/{copy['id']}/package").json()
    assert package["definition_id"] == copy["id"]
    assert package["definition_id"] != entry["package"]["definition_id"]


def test_resync_bumps_version_and_refreshes_the_package(client: TestClient) -> None:
    mission_id = _create_mission(client)
    entry = client.post("/api/library", json={"mission_id": mission_id}).json()

    edited = _mission_payload()
    edited["name"] = "Morning Spray (revised)"
    client.put(f"/api/missions/{mission_id}", json=edited)

    # Until the operator asks, the saved mission keeps its own snapshot.
    held = client.get(f"/api/library/{entry['entry_id']}").json()
    assert held["definition"]["name"] == "Morning Spray"

    resynced = client.post(f"/api/library/{entry['entry_id']}/resync").json()
    assert resynced["definition"]["name"] == "Morning Spray (revised)"
    assert resynced["version"] == entry["version"] + 1
    assert resynced["definition_version"] == resynced["package_definition_version"]
    assert resynced["package_stale"] is False


def test_entry_reports_a_stale_package_instead_of_replanning() -> None:
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray"},
        package={"definition_id": "m1"},
        definition_version=2,
        package_definition_version=1,
    )
    assert entry.package_stale is True
    # Execution still runs the package that was actually reviewed.
    assert resolve_package(entry) == entry.package


# ----------------------------------------------------------------------
# Scheduler: recurrence, multiple daily occurrences, enable/disable
# ----------------------------------------------------------------------

def test_multiple_occurrences_per_day_are_separate_moments() -> None:
    day = date.today() + timedelta(days=1)
    schedule = ScheduleEntry(
        entry_id="lib_1",
        start_date=day.isoformat(),
        times=["06:00", "12:00", "16:00"],
    )
    moments = occurrences(schedule, _at(day, "00:00"))
    assert moments == [_at(day, "06:00"), _at(day, "12:00"), _at(day, "16:00")]


def test_daily_and_weekly_and_custom_recurrence() -> None:
    start = date.today()
    daily = ScheduleEntry(
        entry_id="lib_1",
        start_date=start.isoformat(),
        times=["06:00"],
        recurrence=Recurrence.DAILY,
    )
    moments = occurrences(daily, _at(start, "00:00"), limit=3)
    assert moments == [
        _at(start, "06:00"),
        _at(start + timedelta(days=1), "06:00"),
        _at(start + timedelta(days=2), "06:00"),
    ]

    weekly = ScheduleEntry(
        entry_id="lib_1",
        start_date=start.isoformat(),
        times=["06:00"],
        recurrence=Recurrence.WEEKLY,
        weekdays=[start.weekday()],
    )
    weekly_moments = occurrences(weekly, _at(start, "00:00"), limit=2)
    assert weekly_moments == [
        _at(start, "06:00"),
        _at(start + timedelta(days=7), "06:00"),
    ]

    custom = ScheduleEntry(
        entry_id="lib_1",
        start_date=start.isoformat(),
        times=["06:00"],
        recurrence=Recurrence.CUSTOM,
        interval_days=3,
    )
    assert occurrences(custom, _at(start, "00:00"), limit=2) == [
        _at(start, "06:00"),
        _at(start + timedelta(days=3), "06:00"),
    ]

    one_time = ScheduleEntry(
        entry_id="lib_1", start_date=start.isoformat(), times=["06:00"]
    )
    assert occurrences(one_time, _at(start, "00:00"), limit=5) == [_at(start, "06:00")]


def test_schedule_validation_rejects_incomplete_intent() -> None:
    with pytest.raises(ScheduleError):
        validate_schedule(
            ScheduleEntry(entry_id="", start_date="2026-01-01", times=["06:00"])
        )
    with pytest.raises(ScheduleError):
        validate_schedule(
            ScheduleEntry(entry_id="lib_1", start_date="2026-01-01", times=[])
        )
    with pytest.raises(ScheduleError):
        validate_schedule(
            ScheduleEntry(entry_id="lib_1", start_date="not-a-date", times=["06:00"])
        )
    with pytest.raises(ScheduleError):
        validate_schedule(
            ScheduleEntry(
                entry_id="lib_1",
                start_date="2026-01-01",
                times=["06:00"],
                recurrence=Recurrence.WEEKLY,
            )
        )


def test_schedule_crud_and_enable_disable(client: TestClient) -> None:
    entry = _save_entry(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/schedules",
        json={
            "entry_id": entry["entry_id"],
            "label": "Morning passes",
            "start_date": tomorrow,
            "times": ["06:00", "12:00", "16:00"],
            "recurrence": Recurrence.DAILY.value,
        },
    )
    assert created.status_code == 201
    schedule = created.json()
    assert schedule["times"] == ["06:00", "12:00", "16:00"]
    assert schedule["next_occurrence_ms"] is not None
    assert len(schedule["upcoming_ms"]) == 5

    disabled = client.post(
        f"/api/schedules/{schedule['schedule_id']}/enabled", json={"enabled": False}
    ).json()
    assert disabled["enabled"] is False
    reread = client.get(f"/api/schedules/{schedule['schedule_id']}").json()
    assert reread["enabled"] is False

    updated = client.put(
        f"/api/schedules/{schedule['schedule_id']}",
        json={
            "entry_id": entry["entry_id"],
            "start_date": tomorrow,
            "times": ["07:30"],
            "recurrence": Recurrence.ONE_TIME.value,
        },
    ).json()
    assert updated["times"] == ["07:30"]
    assert updated["recurrence"] == Recurrence.ONE_TIME.value

    assert client.delete(f"/api/schedules/{schedule['schedule_id']}").status_code == 200
    assert client.get("/api/schedules").json()["schedules"] == []


def test_schedule_endpoints_reject_unknown_references(client: TestClient) -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    missing_entry = client.post(
        "/api/schedules",
        json={"entry_id": "lib_missing", "start_date": tomorrow, "times": ["06:00"]},
    )
    assert missing_entry.status_code == 404

    entry = _save_entry(client)
    bad_time = client.post(
        "/api/schedules",
        json={
            "entry_id": entry["entry_id"],
            "start_date": tomorrow,
            "times": ["25:00"],
        },
    )
    assert bad_time.status_code == 400
    assert client.get("/api/schedules/nope").status_code == 404


def test_disabled_schedules_are_not_dispatched() -> None:
    now = int(datetime.now().timestamp() * 1000)
    schedule = ScheduleEntry(
        entry_id="lib_1",
        start_date=date.today().isoformat(),
        times=[datetime.fromtimestamp((now - MINUTE_MS) / 1000).strftime("%H:%M")],
        enabled=False,
    )
    gateway = _StubGateway()
    results = dispatch_due_schedules([schedule], lambda _: None, gateway)
    assert results == []
    assert gateway.deployed == []


def test_due_occurrence_dispatches_once_and_surfaces_missing_entries() -> None:
    now = datetime.now()
    clock = (now - timedelta(minutes=1)).strftime("%H:%M")
    schedule = ScheduleEntry(
        entry_id="lib_missing",
        start_date=now.date().isoformat(),
        times=[clock],
    )
    gateway = _StubGateway()

    first = dispatch_due_schedules([schedule], lambda _: None, gateway)
    assert len(first) == 1
    assert first[0][1] is None
    assert "no longer exists" in schedule.last_result

    # The same occurrence is never dispatched twice.
    assert dispatch_due_schedules([schedule], lambda _: None, gateway) == []


def test_scheduled_dispatch_executes_the_stored_package() -> None:
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray", "field": {"name": "North Vineyard"}},
        package={"definition_id": "m1", "routes": [{"drone_id": 1}]},
        package_definition_version=1,
    )
    now = datetime.now()
    schedule = ScheduleEntry(
        entry_id=entry.entry_id,
        start_date=now.date().isoformat(),
        times=[(now - timedelta(minutes=1)).strftime("%H:%M")],
    )
    gateway = _StubGateway()

    results = dispatch_due_schedules([schedule], lambda _: entry, gateway)
    assert len(results) == 1
    record = results[0][1]
    assert record is not None
    assert record.trigger is ExecutionTrigger.SCHEDULED
    assert record.schedule_id == schedule.schedule_id
    assert gateway.deployed == [entry.package]
    assert gateway.starts == 1
    assert "executed" in schedule.last_result


# ----------------------------------------------------------------------
# Execution preparation & Digital Twin handoff
# ----------------------------------------------------------------------

def test_execute_now_transfers_package_and_starts_the_twin(
    client: TestClient,
) -> None:
    entry = _save_entry(client)
    before = client.get("/api/mission/status").json()
    assert before["status"] != "RUNNING"

    resp = client.post(f"/api/library/{entry['entry_id']}/execute", json={})
    assert resp.status_code == 201
    body = resp.json()
    execution = body["execution"]

    assert body["receipt"]["accepted"] is True
    assert execution["status"] == ExecutionStatus.RUNNING.value
    assert execution["trigger"] == ExecutionTrigger.MANUAL.value
    assert execution["entry_id"] == entry["entry_id"]
    assert execution["route_count"] == len(entry["package"]["routes"])

    # The Twin holds exactly the reviewed package and is now running it.
    twin = client.get("/api/twin/deployment").json()
    assert twin["deployed"] is True
    assert twin["package"] == entry["package"]
    assert client.get("/api/mission/status").json()["status"] == "RUNNING"


def test_execute_now_without_starting_leaves_the_twin_waiting(
    client: TestClient,
) -> None:
    entry = _save_entry(client)
    resp = client.post(
        f"/api/library/{entry['entry_id']}/execute", json={"start_now": False}
    )
    assert resp.status_code == 201
    assert client.get("/api/twin/deployment").json()["deployed"] is True
    assert client.get("/api/mission/status").json()["status"] != "RUNNING"


def test_execution_conflict_is_surfaced_not_resolved(client: TestClient) -> None:
    entry = _save_entry(client)
    assert client.post(f"/api/library/{entry['entry_id']}/execute", json={}).status_code == 201

    second = client.post(f"/api/library/{entry['entry_id']}/execute", json={})
    assert second.status_code == 409
    assert "running" in second.json()["detail"].lower()
    # Exactly one execution was recorded — nothing was queued or rescheduled.
    assert len(client.get("/api/executions").json()["executions"]) == 1


def test_prepare_execution_refuses_a_busy_runtime() -> None:
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray"},
        package={"definition_id": "m1", "routes": []},
    )
    gateway = _StubGateway(status="RUNNING")
    with pytest.raises(ExecutionConflict):
        prepare_execution(entry, entry.package or {}, gateway, ExecutionTrigger.MANUAL)
    assert gateway.deployed == []
    assert gateway.starts == 0


def test_deployed_package_drives_mission_geometry(client: TestClient) -> None:
    """Mission Control renders the executed package, not the demo route."""
    fallback = client.get("/api/mission/geometry").json()
    entry = _save_entry(client)
    client.post(f"/api/library/{entry['entry_id']}/execute", json={})

    geometry = client.get("/api/mission/geometry").json()
    assert geometry["field_polygon"] != fallback["field_polygon"]
    assert geometry["planned_routes"] != fallback["planned_routes"]
    route_counts = {
        did: len(points) for did, points in geometry["planned_routes"].items()
    }
    package_waypoints = {
        str(index + 1): len(route["waypoints"])
        for index, route in enumerate(entry["package"]["execution"]["routes_m"])
    }
    for did, count in package_waypoints.items():
        assert route_counts[did] == count


def test_execution_history_is_separate_from_templates(client: TestClient) -> None:
    entry = _save_entry(client)
    client.post(f"/api/library/{entry['entry_id']}/execute", json={})

    history = client.get("/api/executions").json()["executions"]
    assert len(history) == 1
    record = history[0]
    assert record["mission_name"] == entry["name"]
    assert record["field_name"] == "North Vineyard"
    assert record["operation_type"] == "spray"
    assert record["products"] == ["Herbicide A"]
    assert record["planned"]["coverage_pct"] is not None

    # The template is untouched and still reusable.
    after = client.get(f"/api/library/{entry['entry_id']}").json()
    assert after["definition"] == entry["definition"]
    assert after["package"] == entry["package"]
    assert after["status"] == EntryStatus.READY.value
    assert "status" not in after["summary"]

    detail = client.get(f"/api/executions/{record['execution_id']}").json()
    assert detail["execution_id"] == record["execution_id"]
    assert client.get("/api/executions/nope").status_code == 404


def test_runtime_state_closes_the_history_record() -> None:
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray"},
        package={"definition_id": "m1", "routes": []},
    )
    record = execution_from_package(
        entry, entry.package or {}, ExecutionTrigger.MANUAL
    )
    assert record.status is ExecutionStatus.RUNNING

    apply_runtime_state(record, {"status": "RUNNING", "progress": 0.4, "events": []})
    assert record.status is ExecutionStatus.RUNNING
    assert record.runtime["progress"] == 0.4

    apply_runtime_state(
        record,
        {
            "status": "COMPLETED",
            "progress": 1.0,
            "events": [{"message": "Mission coverage complete"}],
            "end_ms": record.started_ms + 1000,
        },
    )
    assert record.status is ExecutionStatus.COMPLETED
    assert record.duration_ms == 1000
    assert record.runtime["last_event"] == "Mission coverage complete"


def test_open_record_never_inherits_another_missions_outcome() -> None:
    """A killed run must not be closed by whatever the runtime does next.

    Phase 10D.8 recovery testing: after the backend was interrupted mid-run the
    Digital Twin restarted on the standing demo mission, and the open history
    record was closed as COMPLETED at 100% from that unrelated mission.
    """
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray"},
        package={"definition_id": "mission_real", "routes": []},
    )
    record = execution_from_package(
        entry, entry.package or {}, ExecutionTrigger.MANUAL
    )
    apply_runtime_state(
        record,
        {
            "mission_id": "mission_real",
            "status": "RUNNING",
            "progress": 0.12,
            "events": [],
        },
    )
    assert record.status is ExecutionStatus.RUNNING

    changed = apply_runtime_state(
        record,
        {
            "mission_id": "mission-alpha-001",
            "status": "COMPLETED",
            "progress": 1.0,
            "events": [{"message": "Mission coverage complete"}],
        },
    )

    assert changed is True
    assert record.status is ExecutionStatus.INTERRUPTED
    assert record.ended_ms is not None
    assert record.runtime["status"] == "INTERRUPTED"
    assert record.runtime["progress"] == 0.12
    assert "Mission coverage complete" not in str(record.runtime["last_event"])

    # Closed records are left alone by later foreign runtime states.
    assert (
        apply_runtime_state(
            record, {"mission_id": "mission-alpha-001", "status": "RUNNING"}
        )
        is False
    )
    assert record.status is ExecutionStatus.INTERRUPTED


def test_deployed_but_unstarted_runtime_leaves_the_record_open() -> None:
    """An idle runtime holding a deployed package is not "another mission"."""
    entry = LibraryEntry(
        name="Morning Spray",
        definition={"name": "Morning Spray"},
        package={"definition_id": "mission_real", "routes": []},
    )
    record = execution_from_package(
        entry, entry.package or {}, ExecutionTrigger.MANUAL
    )

    apply_runtime_state(
        record, {"mission_id": None, "status": "IDLE", "progress": 0.0, "events": []}
    )

    assert record.status is ExecutionStatus.RUNNING
    assert record.ended_ms is None


def test_execution_requires_a_gateway(tmp_path) -> None:
    from fastapi import FastAPI

    from backend.mission_pipeline.library_api import create_library_router

    store = InMemoryDefinitionStore()
    entry = store.save_library_entry(
        LibraryEntry(name="Morning Spray", definition={"name": "Morning Spray"})
    )
    app = FastAPI()
    app.include_router(create_library_router(store))
    standalone = TestClient(app)

    resp = standalone.post(f"/api/library/{entry.entry_id}/execute", json={})
    assert resp.status_code == 503
    assert standalone.get("/api/library").json()["entries"][0]["name"] == "Morning Spray"


# ----------------------------------------------------------------------
# Boundaries
# ----------------------------------------------------------------------

def test_library_and_scheduler_import_no_runtime_modules() -> None:
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
    root = pathlib.Path(library_module.__file__).parent
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


def test_browsing_the_library_never_touches_runtime_state(client: TestClient) -> None:
    entry = _save_entry(client)
    before = client.get("/api/twin/state").json()

    client.get("/api/library")
    client.get(f"/api/library/{entry['entry_id']}")
    client.get("/api/schedules")
    client.get("/api/executions")
    client.post(f"/api/library/{entry['entry_id']}/duplicate", json={})

    after = client.get("/api/twin/state").json()
    assert before["mission_status"] == after["mission_status"]
    assert client.get("/api/twin/deployment").json()["deployed"] is False


def test_next_occurrence_of_a_past_one_time_schedule_is_none() -> None:
    past = date.today() - timedelta(days=2)
    schedule = ScheduleEntry(
        entry_id="lib_1", start_date=past.isoformat(), times=["06:00"]
    )
    assert next_occurrence(schedule, int(datetime.now().timestamp() * 1000)) is None
