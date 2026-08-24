"""
Mission Definition Pipeline — Mission Library & Scheduler (Phase 10D.7).

Three persisted, deliberately separate concepts:

    LibraryEntry    a reusable saved mission (template): a frozen snapshot of a
                    Mission Definition plus the Mission Package the Planning
                    Core produced for it. Reusable forever; never overwritten
                    by execution state.
    ScheduleEntry   explicit operator scheduling intent for a library entry:
                    date, times (one or more per day), recurrence, enabled.
    ExecutionRecord one past/ongoing execution of a library entry. Execution
                    history — kept apart from the templates it came from.

Boundary:
    * Nothing here plans, optimizes, allocates, schedules *for* the operator or
      decides feasibility. Packages are stored and retrieved verbatim; routes
      are never generated or modified. Planning stays in core/.
    * The scheduler stores the operator's chosen times and reports which
      occurrences are due. It never picks a better time, never reschedules and
      never resolves a conflict — conflicts are surfaced (see execution.py).
    * No runtime module is imported. The Digital Twin is reached only through
      the gateway protocol in execution.py.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, time as time_cls, timedelta
from enum import Enum
from typing import Optional

from backend.serializers import JSONObject, JSONValue

# ---------------------------------------------------------------------------
# Mission Library
# ---------------------------------------------------------------------------


class EntryStatus(str, Enum):
    """Lifecycle of a saved mission inside the library."""

    READY = "ready"
    ARCHIVED = "archived"


@dataclass
class LibraryEntry:
    """
    A saved, reusable mission.

    ``definition`` and ``package`` are frozen snapshots of the existing
    contract — the library adds no second mission representation. ``package``
    is the Planning Core output as produced for ``package_definition_version``;
    if the entry's definition is later updated the package is *not* recomputed
    silently, it is reported stale (see ``package_stale``) so the operator can
    re-run the Planning Core explicitly.
    """

    name: str
    definition: JSONObject
    package: Optional[JSONObject] = None
    description: str = ""
    template: bool = True
    status: EntryStatus = EntryStatus.READY
    source_mission_id: str = ""
    definition_version: int = 1
    package_definition_version: Optional[int] = None
    entry_id: str = field(default_factory=lambda: f"lib_{uuid.uuid4().hex[:12]}")
    version: int = 1
    created_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    @property
    def package_stale(self) -> bool:
        """True when the stored package predates the stored definition."""
        if self.package is None:
            return False
        return self.package_definition_version != self.definition_version

    def to_json(self) -> JSONObject:
        return {
            "entry_id": self.entry_id,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "status": self.status.value,
            "source_mission_id": self.source_mission_id,
            "definition": self.definition,
            "definition_version": self.definition_version,
            "package": self.package,
            "package_definition_version": self.package_definition_version,
            "package_stale": self.package_stale,
            "version": self.version,
            "created_ms": self.created_ms,
            "updated_ms": self.updated_ms,
            "summary": summarize_definition(self.definition, self.package),
        }

    @classmethod
    def from_json(cls, data: JSONObject) -> "LibraryEntry":
        entry = cls(
            name=_as_str(data.get("name"), "Saved mission"),
            definition=_as_object(data.get("definition")),
            package=_as_opt_object(data.get("package")),
            description=_as_str(data.get("description"), ""),
            template=bool(data.get("template", True)),
            status=_status_from(data.get("status")),
            source_mission_id=_as_str(data.get("source_mission_id"), ""),
            definition_version=_as_int(data.get("definition_version"), 1),
            package_definition_version=_as_opt_int(
                data.get("package_definition_version")
            ),
        )
        entry_id = data.get("entry_id")
        if isinstance(entry_id, str) and entry_id:
            entry.entry_id = entry_id
        entry.version = _as_int(data.get("version"), 1)
        entry.created_ms = _as_int(data.get("created_ms"), entry.created_ms)
        entry.updated_ms = _as_int(data.get("updated_ms"), entry.updated_ms)
        return entry


def summarize_definition(
    definition: JSONObject, package: Optional[JSONObject]
) -> JSONObject:
    """
    Projection of already-stored values for list rendering.

    Reads fields out of the definition/package — nothing is derived, computed
    or decided; the counts are plain list lengths.
    """
    field_data = _as_object(definition.get("field"))
    operation = _as_object(definition.get("operation"))
    zones = [z for z in _as_list(field_data.get("zones")) if isinstance(z, dict)]
    products = [
        _as_str(_as_object(p).get("name"), "")
        for p in _as_list(definition.get("products"))
    ]
    summary: JSONObject = {
        "field_name": _as_str(field_data.get("name"), ""),
        "crop_type": _as_str(field_data.get("crop_type"), ""),
        "location": _as_str(field_data.get("location"), ""),
        "operation_type": _as_str(operation.get("operation_type"), ""),
        "zone_count": len(zones),
        "products": [p for p in products if p],
        "fleet_count": len(_as_list(definition.get("fleet"))),
        "priority": _as_str(definition.get("priority"), "normal"),
        "area_ha": None,
        "route_count": None,
        "go_no_go": None,
        "estimated_duration": None,
    }
    if package is not None:
        geometry = _as_object(package.get("field_geometry"))
        recommendation = _as_object(package.get("recommendation"))
        resources = _as_object(package.get("resources"))
        summary["area_ha"] = _as_opt_float(geometry.get("area_ha"))
        summary["route_count"] = len(_as_list(package.get("routes")))
        summary["go_no_go"] = _as_opt_str(recommendation.get("go_no_go"))
        summary["estimated_duration"] = _as_opt_str(
            resources.get("mission_duration_formatted")
        )
    return summary


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class Recurrence(str, Enum):
    """Operator-chosen repeat rule. No rule is ever inferred or optimized."""

    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ScheduleError(ValueError):
    """Raised when a schedule cannot be stored as described by the operator."""


#: How far ahead occurrences are enumerated for display.
OCCURRENCE_HORIZON_DAYS = 30


@dataclass
class ScheduleEntry:
    """
    An operator's explicit scheduling intent for one library entry.

    ``times`` holds one or more clock times, so a mission can run several times
    on the same day (06:00 / 12:00 / 16:00); each time is materialized as its
    own occurrence. ``weekdays`` (0 = Monday) applies to weekly recurrence and
    ``interval_days`` to custom recurrence.
    """

    entry_id: str
    start_date: str
    times: list[str]
    recurrence: Recurrence = Recurrence.ONE_TIME
    weekdays: list[int] = field(default_factory=list)
    interval_days: int = 1
    enabled: bool = True
    label: str = ""
    notes: str = ""
    schedule_id: str = field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:12]}")
    last_triggered_ms: Optional[int] = None
    last_result: str = ""
    created_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_json(self) -> JSONObject:
        return {
            "schedule_id": self.schedule_id,
            "entry_id": self.entry_id,
            "label": self.label,
            "notes": self.notes,
            "start_date": self.start_date,
            "times": list(self.times),
            "recurrence": self.recurrence.value,
            "weekdays": list(self.weekdays),
            "interval_days": self.interval_days,
            "enabled": self.enabled,
            "last_triggered_ms": self.last_triggered_ms,
            "last_result": self.last_result,
            "created_ms": self.created_ms,
            "updated_ms": self.updated_ms,
        }

    @classmethod
    def from_json(cls, data: JSONObject) -> "ScheduleEntry":
        entry = cls(
            entry_id=_as_str(data.get("entry_id"), ""),
            start_date=_as_str(data.get("start_date"), ""),
            times=[
                _as_str(t, "")
                for t in _as_list(data.get("times"))
                if isinstance(t, str)
            ],
            recurrence=_recurrence_from(data.get("recurrence")),
            weekdays=[
                int(d)
                for d in _as_list(data.get("weekdays"))
                if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6
            ],
            interval_days=_as_int(data.get("interval_days"), 1),
            enabled=bool(data.get("enabled", True)),
            label=_as_str(data.get("label"), ""),
            notes=_as_str(data.get("notes"), ""),
        )
        schedule_id = data.get("schedule_id")
        if isinstance(schedule_id, str) and schedule_id:
            entry.schedule_id = schedule_id
        entry.last_triggered_ms = _as_opt_int(data.get("last_triggered_ms"))
        entry.last_result = _as_str(data.get("last_result"), "")
        entry.created_ms = _as_int(data.get("created_ms"), entry.created_ms)
        entry.updated_ms = _as_int(data.get("updated_ms"), entry.updated_ms)
        return entry


def validate_schedule(schedule: ScheduleEntry) -> ScheduleEntry:
    """Reject an unusable schedule instead of guessing what the operator meant."""
    if not schedule.entry_id:
        raise ScheduleError("A schedule must reference a saved mission")
    if not schedule.times:
        raise ScheduleError("A schedule must define at least one time")
    for value in schedule.times:
        _parse_time(value)
    _parse_date(schedule.start_date)
    if schedule.recurrence is Recurrence.WEEKLY and not schedule.weekdays:
        raise ScheduleError("A weekly schedule must select at least one weekday")
    if schedule.recurrence is Recurrence.CUSTOM and schedule.interval_days < 1:
        raise ScheduleError("A custom repeat interval must be at least 1 day")
    return schedule


def occurrences(
    schedule: ScheduleEntry,
    from_ms: int,
    horizon_days: int = OCCURRENCE_HORIZON_DAYS,
    limit: int = 20,
) -> list[int]:
    """
    Enumerate the operator's scheduled occurrences (epoch ms), ascending.

    Pure calendar expansion of what the operator typed: every selected day is
    combined with every selected time. No time is chosen, moved or skipped.
    """
    start = _parse_date(schedule.start_date)
    times = sorted(_parse_time(t) for t in schedule.times)
    begin = datetime.fromtimestamp(from_ms / 1000.0)
    horizon = begin + timedelta(days=horizon_days)

    result: list[int] = []
    day = min(start, begin.date())
    last_day = horizon.date()
    while day <= last_day and len(result) < limit:
        if _day_selected(schedule, start, day):
            for clock in times:
                moment = datetime.combine(day, clock)
                if moment >= begin and len(result) < limit:
                    result.append(int(moment.timestamp() * 1000))
        if schedule.recurrence is Recurrence.ONE_TIME and day >= start:
            break
        day += timedelta(days=1)
    return result


def next_occurrence(schedule: ScheduleEntry, from_ms: int) -> Optional[int]:
    """The operator's next scheduled moment, or None when nothing remains."""
    upcoming = occurrences(schedule, from_ms, limit=1)
    return upcoming[0] if upcoming else None


def due_occurrence(schedule: ScheduleEntry, now_ms: int) -> Optional[int]:
    """
    The most recent occurrence that is due and not yet triggered.

    Returns None for disabled schedules — a disabled schedule is simply not
    dispatched; it is never rescheduled or made up for later.
    """
    if not schedule.enabled:
        return None
    since = schedule.last_triggered_ms or 0
    window_start = max(since + 1, now_ms - _lookback_ms())
    candidates = occurrences(
        schedule, window_start, horizon_days=1, limit=_MAX_DUE_SCAN
    )
    due = [ms for ms in candidates if ms <= now_ms and ms > since]
    return due[-1] if due else None


#: Occurrences older than this are not dispatched late (no silent catch-up).
_DUE_LOOKBACK_MINUTES = 10
_MAX_DUE_SCAN = 96


def _lookback_ms() -> int:
    return _DUE_LOOKBACK_MINUTES * 60 * 1000


def _day_selected(
    schedule: ScheduleEntry, start: date_cls, day: date_cls
) -> bool:
    if day < start:
        return False
    if schedule.recurrence is Recurrence.ONE_TIME:
        return day == start
    if schedule.recurrence is Recurrence.DAILY:
        return True
    if schedule.recurrence is Recurrence.WEEKLY:
        return day.weekday() in schedule.weekdays
    interval = max(1, schedule.interval_days)
    return (day - start).days % interval == 0


def _parse_date(value: str) -> date_cls:
    try:
        return date_cls.fromisoformat(value)
    except ValueError as exc:
        raise ScheduleError(f"Invalid schedule date '{value}' (expected YYYY-MM-DD)") from exc


def _parse_time(value: str) -> time_cls:
    try:
        return time_cls.fromisoformat(value)
    except ValueError as exc:
        raise ScheduleError(f"Invalid schedule time '{value}' (expected HH:MM)") from exc


# ---------------------------------------------------------------------------
# Execution history
# ---------------------------------------------------------------------------


class ExecutionStatus(str, Enum):
    """Final state of one execution, mirroring the runtime's own lifecycle."""

    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class ExecutionTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


@dataclass
class ExecutionRecord:
    """
    One execution of a saved mission — history, never a template.

    Planned figures (coverage, resources, duration) are copied from the Mission
    Package that was executed; runtime figures are copied from the Digital Twin
    once it reports them. Nothing is recomputed here.
    """

    entry_id: str
    mission_name: str
    definition_id: str
    trigger: ExecutionTrigger = ExecutionTrigger.MANUAL
    schedule_id: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.RUNNING
    field_name: str = ""
    operation_type: str = ""
    products: list[str] = field(default_factory=list)
    drone_count: int = 0
    route_count: int = 0
    planned: JSONObject = field(default_factory=dict)
    runtime: JSONObject = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    deployment_id: Optional[str] = None
    started_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    ended_ms: Optional[int] = None
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")

    @property
    def duration_ms(self) -> Optional[int]:
        if self.ended_ms is None:
            return None
        return max(0, self.ended_ms - self.started_ms)

    def to_json(self) -> JSONObject:
        return {
            "execution_id": self.execution_id,
            "entry_id": self.entry_id,
            "definition_id": self.definition_id,
            "mission_name": self.mission_name,
            "field_name": self.field_name,
            "operation_type": self.operation_type,
            "products": list(self.products),
            "drone_count": self.drone_count,
            "route_count": self.route_count,
            "trigger": self.trigger.value,
            "schedule_id": self.schedule_id,
            "status": self.status.value,
            "planned": self.planned,
            "runtime": self.runtime,
            "warnings": list(self.warnings),
            "deployment_id": self.deployment_id,
            "started_ms": self.started_ms,
            "ended_ms": self.ended_ms,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_json(cls, data: JSONObject) -> "ExecutionRecord":
        record = cls(
            entry_id=_as_str(data.get("entry_id"), ""),
            mission_name=_as_str(data.get("mission_name"), ""),
            definition_id=_as_str(data.get("definition_id"), ""),
            trigger=_trigger_from(data.get("trigger")),
            schedule_id=_as_opt_str(data.get("schedule_id")),
            status=_exec_status_from(data.get("status")),
            field_name=_as_str(data.get("field_name"), ""),
            operation_type=_as_str(data.get("operation_type"), ""),
            products=[p for p in _as_list(data.get("products")) if isinstance(p, str)],
            drone_count=_as_int(data.get("drone_count"), 0),
            route_count=_as_int(data.get("route_count"), 0),
            planned=_as_object(data.get("planned")),
            runtime=_as_object(data.get("runtime")),
            warnings=[w for w in _as_list(data.get("warnings")) if isinstance(w, str)],
            deployment_id=_as_opt_str(data.get("deployment_id")),
        )
        execution_id = data.get("execution_id")
        if isinstance(execution_id, str) and execution_id:
            record.execution_id = execution_id
        record.started_ms = _as_int(data.get("started_ms"), record.started_ms)
        record.ended_ms = _as_opt_int(data.get("ended_ms"))
        return record


def planned_metrics(package: JSONObject) -> JSONObject:
    """Copy the Planning Core figures this execution was started with."""
    recommendation = _as_object(package.get("recommendation"))
    resources = _as_object(package.get("resources"))
    geometry = _as_object(package.get("field_geometry"))
    return {
        "coverage_pct": _as_opt_float(recommendation.get("coverage_pct")),
        "confidence_pct": _as_opt_float(recommendation.get("confidence_pct")),
        "go_no_go": _as_opt_str(recommendation.get("go_no_go")),
        "duration_formatted": _as_opt_str(resources.get("mission_duration_formatted")),
        "duration_min": _as_opt_float(resources.get("mission_duration_min")),
        "total_liquid_l": _as_opt_float(resources.get("total_liquid_l")),
        "total_battery_cycles": _as_opt_float(resources.get("total_battery_cycles")),
        "area_ha": _as_opt_float(geometry.get("area_ha")),
    }


def execution_from_package(
    entry: LibraryEntry,
    package: JSONObject,
    trigger: ExecutionTrigger,
    schedule_id: Optional[str] = None,
) -> ExecutionRecord:
    """Open a history record for an execution that is about to start."""
    summary = summarize_definition(entry.definition, package)
    return ExecutionRecord(
        entry_id=entry.entry_id,
        mission_name=entry.name,
        definition_id=_as_str(package.get("definition_id"), ""),
        trigger=trigger,
        schedule_id=schedule_id,
        field_name=_as_str(summary.get("field_name"), ""),
        operation_type=_as_str(summary.get("operation_type"), ""),
        products=[p for p in _as_list(summary.get("products")) if isinstance(p, str)],
        drone_count=len(_as_list(entry.definition.get("fleet"))),
        route_count=len(_as_list(package.get("routes"))),
        planned=planned_metrics(package),
        warnings=[
            w
            for w in _as_list(_as_object(package.get("validation")).get("warnings"))
            if isinstance(w, str)
        ],
    )


#: Runtime mission states that close an execution record.
_TERMINAL_RUNTIME_STATES = {"COMPLETED", "ABORTED", "FAILED"}


def apply_runtime_state(
    record: ExecutionRecord, mission_payload: JSONObject
) -> bool:
    """
    Copy the Digital Twin's reported state into a history record.

    Returns True when the record changed. The runtime remains the source of
    truth: this only mirrors ``status``/``progress``/events into history.

    An open record is only ever updated from the runtime mission it belongs to.
    Once the Digital Twin identifies itself with a different mission, this
    execution can no longer reach an outcome of its own, so it is closed as
    interrupted instead of inheriting the other mission's progress.
    """
    if _runtime_runs_other_mission(record, mission_payload):
        if record.status is not ExecutionStatus.RUNNING:
            return False
        record.status = ExecutionStatus.INTERRUPTED
        record.ended_ms = int(time.time() * 1000)
        record.runtime = {
            **record.runtime,
            "status": "INTERRUPTED",
            "last_event": (
                "The Digital Twin stopped reporting this mission before it "
                "finished"
            ),
        }
        return True

    status = _as_str(mission_payload.get("status"), "").upper()
    progress = _as_opt_float(mission_payload.get("progress"))
    events = _as_list(mission_payload.get("events"))
    runtime: JSONObject = {
        "status": status,
        "progress": progress,
        "event_count": len(events),
        "last_event": (
            _as_str(_as_object(events[-1]).get("message"), "") if events else ""
        ),
    }
    changed = runtime != record.runtime
    record.runtime = runtime

    if record.status is ExecutionStatus.RUNNING and status in _TERMINAL_RUNTIME_STATES:
        record.status = (
            ExecutionStatus.COMPLETED
            if status == "COMPLETED"
            else ExecutionStatus.INTERRUPTED
        )
        end_ms = _as_opt_int(mission_payload.get("end_ms"))
        record.ended_ms = end_ms if end_ms is not None else int(time.time() * 1000)
        changed = True
    return changed


# ---------------------------------------------------------------------------
# Typed coercion helpers (no Any / getattr)
# ---------------------------------------------------------------------------


def _runtime_runs_other_mission(
    record: ExecutionRecord, mission_payload: JSONObject
) -> bool:
    """
    True when the runtime reports a mission that is not this execution's.

    A runtime with no active mission (``mission_id`` absent while idle) is not
    "another mission": a deployed package legitimately waits there for the
    operator's start intent.
    """
    runtime_mission_id = _as_opt_str(mission_payload.get("mission_id"))
    if not record.definition_id or runtime_mission_id is None:
        return False
    return runtime_mission_id != record.definition_id


def _status_from(value: JSONValue) -> EntryStatus:
    if isinstance(value, str):
        try:
            return EntryStatus(value)
        except ValueError:
            return EntryStatus.READY
    return EntryStatus.READY


def _recurrence_from(value: JSONValue) -> Recurrence:
    if isinstance(value, str):
        try:
            return Recurrence(value)
        except ValueError:
            return Recurrence.ONE_TIME
    return Recurrence.ONE_TIME


def _trigger_from(value: JSONValue) -> ExecutionTrigger:
    if isinstance(value, str):
        try:
            return ExecutionTrigger(value)
        except ValueError:
            return ExecutionTrigger.MANUAL
    return ExecutionTrigger.MANUAL


def _exec_status_from(value: JSONValue) -> ExecutionStatus:
    if isinstance(value, str):
        try:
            return ExecutionStatus(value)
        except ValueError:
            return ExecutionStatus.RUNNING
    return ExecutionStatus.RUNNING


def _as_str(value: JSONValue, default: str) -> str:
    return value if isinstance(value, str) else default


def _as_opt_str(value: JSONValue) -> Optional[str]:
    return value if isinstance(value, str) else None


def _as_int(value: JSONValue, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _as_opt_int(value: JSONValue) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_opt_float(value: JSONValue) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_object(value: JSONValue) -> JSONObject:
    return value if isinstance(value, dict) else {}


def _as_opt_object(value: JSONValue) -> Optional[JSONObject]:
    return value if isinstance(value, dict) else None


def _as_list(value: JSONValue) -> list[JSONValue]:
    return value if isinstance(value, list) else []
