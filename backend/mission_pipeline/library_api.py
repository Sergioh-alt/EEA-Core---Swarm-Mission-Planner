"""
Mission Definition Pipeline — Mission Library & Scheduler REST API (10D.7).

Contract:
    GET    /api/library                          -> saved missions (templates)
    POST   /api/library                          -> save a mission as reusable
    GET    /api/library/{entry_id}               -> definition + Mission Package
    PUT    /api/library/{entry_id}               -> metadata only (name, ...)
    DELETE /api/library/{entry_id}               -> remove a saved mission
    POST   /api/library/{entry_id}/resync        -> re-snapshot from its source
                                                    mission (new entry version)
    POST   /api/library/{entry_id}/duplicate     -> new Mission Definition
    POST   /api/library/{entry_id}/execute       -> execution preparation

    GET    /api/schedules                        -> schedules + next occurrences
    POST   /api/schedules                        -> create a schedule
    GET    /api/schedules/{schedule_id}
    PUT    /api/schedules/{schedule_id}
    DELETE /api/schedules/{schedule_id}
    POST   /api/schedules/{schedule_id}/enabled  -> enable / disable

    GET    /api/executions                       -> execution history
    GET    /api/executions/{execution_id}

Boundaries: the library persists and retrieves the existing Mission Definition
/ Mission Package contract; the scheduler persists explicit operator intent.
Neither plans, optimizes, allocates, resolves conflicts or owns runtime state.
The Digital Twin is reached only via the injected execution gateway.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.mission_pipeline.execution import (
    ExecutionConflict,
    ExecutionError,
    MissionExecutionGateway,
    dispatch_due_schedules,
    prepare_execution,
    resolve_package,
)
from backend.mission_pipeline.library import (
    EntryStatus,
    ExecutionRecord,
    ExecutionTrigger,
    LibraryEntry,
    ScheduleEntry,
    ScheduleError,
    apply_runtime_state,
    next_occurrence,
    occurrences,
    validate_schedule,
)
from backend.mission_pipeline.models import (
    DefinitionValidationError,
    MissionDefinition,
)
from backend.mission_pipeline.persistence import DefinitionStore, NotFoundError
from backend.mission_pipeline.planning_core import build_mission_package
from backend.serializers import JSONObject, JSONValue

#: How many upcoming occurrences are listed per schedule.
OCCURRENCE_PREVIEW = 5


async def _read_json_object(request: Request) -> JSONObject:
    body = await request.json()
    if not isinstance(body, dict):
        raise DefinitionValidationError("Request body must be a JSON object")
    return body


def schedule_view(schedule: ScheduleEntry, now_ms: int) -> JSONObject:
    """A schedule plus the occurrences the operator's own rule produces."""
    view = schedule.to_json()
    view["next_occurrence_ms"] = next_occurrence(schedule, now_ms)
    view["upcoming_ms"] = occurrences(schedule, now_ms, limit=OCCURRENCE_PREVIEW)
    return view


def refresh_open_executions(
    store: DefinitionStore, gateway: MissionExecutionGateway
) -> list[ExecutionRecord]:
    """
    Mirror the Digital Twin's reported state into open history records.

    History follows the runtime; it never drives it. Only the most recent open
    record can correspond to the single runtime mission, so older open records
    are left as they are.
    """
    records = [r for r in store.list_executions() if r.status.value == "running"]
    if not records:
        return []
    payload = gateway.get_mission_payload()
    updated: list[ExecutionRecord] = []
    for record in records[:1]:
        if apply_runtime_state(record, payload):
            store.save_execution(record)
            updated.append(record)
    return updated


def dispatch_scheduled_missions(
    store: DefinitionStore, gateway: MissionExecutionGateway
) -> list[ExecutionRecord]:
    """Execute the operator's due occurrences and persist what happened."""

    def resolve_entry(entry_id: str) -> Optional[LibraryEntry]:
        try:
            return store.get_library_entry(entry_id)
        except NotFoundError:
            return None

    started: list[ExecutionRecord] = []
    for schedule, record in dispatch_due_schedules(
        store.list_schedules(), resolve_entry, gateway
    ):
        store.save_schedule(schedule)
        if record is not None:
            store.save_execution(record)
            started.append(record)
    return started


def create_library_router(
    store: DefinitionStore,
    execution_gateway: Optional[MissionExecutionGateway] = None,
) -> APIRouter:
    """
    Build the Mission Library & Scheduler router bound to its store.

    ``execution_gateway`` is the Digital Twin interface; it is injected, never
    imported, so the library keeps no runtime dependency. Without it the
    library and scheduler still work — only execution is unavailable.
    """
    router = APIRouter()

    def _entry(entry_id: str) -> Optional[LibraryEntry]:
        try:
            return store.get_library_entry(entry_id)
        except NotFoundError:
            return None

    # -- Mission Library -----------------------------------------------------

    @router.get("/api/library")
    async def list_library() -> JSONResponse:
        return JSONResponse(
            {"entries": [e.to_json() for e in store.list_library_entries()]}
        )

    @router.post("/api/library")
    async def save_to_library(request: Request) -> JSONResponse:
        """
        Save an existing Mission Definition as a reusable mission.

        The Planning Core produces the package that is stored alongside the
        definition snapshot, so the library never invents planning output.
        """
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))

        mission_id = body.get("mission_id")
        if not isinstance(mission_id, str) or not mission_id:
            return _bad_request("'mission_id' is required")
        try:
            definition = store.get_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)

        package = _package_for(store, definition)
        entry = LibraryEntry(
            name=_str_or(body.get("name"), definition.name),
            definition=definition.to_json(),
            package=package,
            description=_str_or(body.get("description"), definition.description),
            template=bool(body.get("template", True)),
            source_mission_id=definition.id,
            definition_version=definition.version,
            package_definition_version=definition.version,
        )
        return JSONResponse(store.save_library_entry(entry).to_json(), status_code=201)

    @router.get("/api/library/{entry_id}")
    async def get_entry(entry_id: str) -> JSONResponse:
        entry = _entry(entry_id)
        if entry is None:
            return _not_found("saved mission", entry_id)
        return JSONResponse(entry.to_json())

    @router.put("/api/library/{entry_id}")
    async def update_entry(entry_id: str, request: Request) -> JSONResponse:
        """Update library metadata only — never the definition or package."""
        entry = _entry(entry_id)
        if entry is None:
            return _not_found("saved mission", entry_id)
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))

        entry.name = _str_or(body.get("name"), entry.name)
        entry.description = _str_or(body.get("description"), entry.description)
        if isinstance(body.get("template"), bool):
            entry.template = bool(body["template"])
        status = body.get("status")
        if isinstance(status, str):
            try:
                entry.status = EntryStatus(status)
            except ValueError:
                return _bad_request(f"unknown status '{status}'")
        return JSONResponse(store.save_library_entry(entry).to_json())

    @router.delete("/api/library/{entry_id}")
    async def delete_entry(entry_id: str) -> JSONResponse:
        try:
            store.delete_library_entry(entry_id)
        except NotFoundError:
            return _not_found("saved mission", entry_id)
        return JSONResponse({"deleted": entry_id})

    @router.post("/api/library/{entry_id}/resync")
    async def resync_entry(entry_id: str) -> JSONResponse:
        """
        Re-snapshot a saved mission from its source Mission Definition.

        Explicit operator action: the stored package is replaced by a freshly
        planned one for the current definition and the entry version is bumped,
        so an already-executed package is never changed retroactively.
        """
        entry = _entry(entry_id)
        if entry is None:
            return _not_found("saved mission", entry_id)
        try:
            definition = store.get_definition(entry.source_mission_id)
        except NotFoundError:
            return _not_found("mission", entry.source_mission_id)

        entry.definition = definition.to_json()
        entry.definition_version = definition.version
        entry.package = _package_for(store, definition)
        entry.package_definition_version = definition.version
        entry.version += 1
        return JSONResponse(store.save_library_entry(entry).to_json())

    @router.post("/api/library/{entry_id}/duplicate")
    async def duplicate_entry(entry_id: str, request: Request) -> JSONResponse:
        """
        Create a new, editable Mission Definition from a saved mission.

        The saved mission is never mutated: the copy gets a new identity and
        starts at version 1, and the operator re-runs the Planning Core on it.
        """
        entry = _entry(entry_id)
        if entry is None:
            return _not_found("saved mission", entry_id)
        try:
            body = await _read_json_object(request)
        except ValueError:
            body = {}
        except DefinitionValidationError as exc:
            return _bad_request(str(exc))

        source = dict(entry.definition)
        source.pop("id", None)
        source["version"] = 1
        source["name"] = _str_or(body.get("name"), f"{entry.name} (copy)")
        try:
            copy = MissionDefinition.from_json(source)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        stored = store.save_definition(copy)
        return JSONResponse(
            {"mission": stored.to_json(), "source_entry_id": entry.entry_id},
            status_code=201,
        )

    @router.post("/api/library/{entry_id}/execute")
    async def execute_entry(entry_id: str, request: Request) -> JSONResponse:
        """
        Execution preparation: hand this saved mission's package to the Twin.

        The package is transferred verbatim through the deployment boundary and
        the operator's start intent follows unless ``start_now`` is false.
        """
        entry = _entry(entry_id)
        if entry is None:
            return _not_found("saved mission", entry_id)
        if execution_gateway is None:
            return _unavailable("Digital Twin execution interface is unavailable")
        try:
            body = await _read_json_object(request)
        except ValueError:
            body = {}
        except DefinitionValidationError as exc:
            return _bad_request(str(exc))

        start_now = body.get("start_now")
        try:
            record, receipt = prepare_execution(
                entry,
                resolve_package(entry),
                execution_gateway,
                ExecutionTrigger.MANUAL,
                start_now=True if not isinstance(start_now, bool) else start_now,
            )
        except ExecutionConflict as exc:
            return _conflict(str(exc))
        except ExecutionError as exc:
            return _bad_request(str(exc))
        store.save_execution(record)
        return JSONResponse(
            {"execution": record.to_json(), "receipt": receipt}, status_code=201
        )

    # -- Scheduler -----------------------------------------------------------

    @router.get("/api/schedules")
    async def list_schedules() -> JSONResponse:
        now_ms = int(time.time() * 1000)
        return JSONResponse(
            {"schedules": [schedule_view(s, now_ms) for s in store.list_schedules()]}
        )

    @router.post("/api/schedules")
    async def create_schedule(request: Request) -> JSONResponse:
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        try:
            schedule = validate_schedule(ScheduleEntry.from_json(body))
        except ScheduleError as exc:
            return _bad_request(str(exc))
        if _entry(schedule.entry_id) is None:
            return _not_found("saved mission", schedule.entry_id)
        stored = store.save_schedule(schedule)
        return JSONResponse(
            schedule_view(stored, int(time.time() * 1000)), status_code=201
        )

    @router.get("/api/schedules/{schedule_id}")
    async def get_schedule(schedule_id: str) -> JSONResponse:
        try:
            schedule = store.get_schedule(schedule_id)
        except NotFoundError:
            return _not_found("schedule", schedule_id)
        return JSONResponse(schedule_view(schedule, int(time.time() * 1000)))

    @router.put("/api/schedules/{schedule_id}")
    async def update_schedule(schedule_id: str, request: Request) -> JSONResponse:
        try:
            existing = store.get_schedule(schedule_id)
        except NotFoundError:
            return _not_found("schedule", schedule_id)
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))

        body["schedule_id"] = schedule_id
        body.setdefault("entry_id", existing.entry_id)
        try:
            schedule = validate_schedule(ScheduleEntry.from_json(body))
        except ScheduleError as exc:
            return _bad_request(str(exc))
        if _entry(schedule.entry_id) is None:
            return _not_found("saved mission", schedule.entry_id)
        schedule.created_ms = existing.created_ms
        schedule.last_triggered_ms = existing.last_triggered_ms
        schedule.last_result = existing.last_result
        stored = store.save_schedule(schedule)
        return JSONResponse(schedule_view(stored, int(time.time() * 1000)))

    @router.post("/api/schedules/{schedule_id}/enabled")
    async def set_schedule_enabled(
        schedule_id: str, request: Request
    ) -> JSONResponse:
        try:
            schedule = store.get_schedule(schedule_id)
        except NotFoundError:
            return _not_found("schedule", schedule_id)
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            return _bad_request("'enabled' must be a boolean")
        schedule.enabled = enabled
        stored = store.save_schedule(schedule)
        return JSONResponse(schedule_view(stored, int(time.time() * 1000)))

    @router.delete("/api/schedules/{schedule_id}")
    async def delete_schedule(schedule_id: str) -> JSONResponse:
        try:
            store.delete_schedule(schedule_id)
        except NotFoundError:
            return _not_found("schedule", schedule_id)
        return JSONResponse({"deleted": schedule_id})

    # -- Execution history ---------------------------------------------------

    @router.get("/api/executions")
    async def list_executions() -> JSONResponse:
        if execution_gateway is not None:
            refresh_open_executions(store, execution_gateway)
        return JSONResponse(
            {"executions": [r.to_json() for r in store.list_executions()]}
        )

    @router.get("/api/executions/{execution_id}")
    async def get_execution(execution_id: str) -> JSONResponse:
        try:
            record = store.get_execution(execution_id)
        except NotFoundError:
            return _not_found("execution", execution_id)
        return JSONResponse(record.to_json())

    return router


def _package_for(store: DefinitionStore, definition: MissionDefinition) -> JSONObject:
    """
    The Mission Package to snapshot for a definition.

    A deployed mission is locked, so its immutable package is stored verbatim;
    otherwise the Planning Core produces one from the definition.
    """
    try:
        record = store.get_deployment(definition.id)
    except NotFoundError:
        record = None
    if record is not None and record.is_locked and record.package is not None:
        return record.package
    return build_mission_package(definition).to_json()


def _str_or(value: JSONValue, fallback: str) -> str:
    return value if isinstance(value, str) and value.strip() else fallback


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse({"error": "bad_request", "detail": message}, status_code=400)


def _conflict(message: str) -> JSONResponse:
    return JSONResponse({"error": "conflict", "detail": message}, status_code=409)


def _unavailable(message: str) -> JSONResponse:
    return JSONResponse({"error": "unavailable", "detail": message}, status_code=503)


def _not_found(kind: str, identifier: str) -> JSONResponse:
    return JSONResponse(
        {"error": "not_found", "detail": f"{kind} '{identifier}' not found"},
        status_code=404,
    )


__all__ = [
    "create_library_router",
    "dispatch_scheduled_missions",
    "refresh_open_executions",
    "schedule_view",
]
