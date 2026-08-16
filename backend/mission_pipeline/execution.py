"""
Mission Definition Pipeline — Execution Preparation (Phase 10D.7).

The single path from a saved mission to the running Digital Twin:

    Library entry -> Mission Package -> deployment -> operator start intent

Boundary:
    * The package is transferred verbatim. Nothing here generates or modifies
      routes, allocates drones, rebalances resources or re-times anything —
      those are Planning Core outputs and stay untouched.
    * No runtime module is imported. The Digital Twin is reached exclusively
      through ``MissionExecutionGateway``, which the composition root binds to
      the runtime (see backend/twin_server.py).
    * Conflicts (a mission already running, a missing package) are raised and
      surfaced to the operator. They are never resolved automatically and no
      occurrence is silently rescheduled.
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Protocol

from backend.mission_pipeline.library import (
    ExecutionRecord,
    ExecutionTrigger,
    LibraryEntry,
    ScheduleEntry,
    apply_runtime_state,
    due_occurrence,
    execution_from_package,
)
from backend.mission_pipeline.models import MissionDefinition
from backend.mission_pipeline.planning_core import build_mission_package
from backend.serializers import JSONObject

#: Runtime mission states that block starting another execution.
BUSY_RUNTIME_STATES = frozenset({"RUNNING", "PAUSED"})


class ExecutionError(RuntimeError):
    """Raised when an execution cannot be prepared as requested."""


class ExecutionConflict(ExecutionError):
    """
    Raised when the runtime cannot accept this execution right now.

    Surfaced to the operator verbatim: the scheduler does not queue, retry or
    move the occurrence.
    """


class MissionExecutionGateway(Protocol):
    """
    The Digital Twin interface used by execution preparation.

    Implemented by the runtime. ``deploy_mission_package`` is the same transfer
    boundary Mission Review uses (Phase 10D.6); ``start_mission`` is the
    existing operator START intent, invoked only when the operator explicitly
    chose "Execute now" or configured a schedule that has come due.
    """

    def deploy_mission_package(self, package: JSONObject) -> JSONObject: ...

    def start_mission(self) -> bool: ...

    def get_mission_payload(self) -> JSONObject: ...


def resolve_package(entry: LibraryEntry) -> JSONObject:
    """
    The Mission Package to execute for a saved mission.

    Prefers the package stored with the entry so an execution runs exactly the
    planning result the operator reviewed. Only when no package was ever stored
    is the Planning Core asked for one — the library itself never plans.
    """
    if entry.package is not None:
        return dict(entry.package)
    definition = MissionDefinition.from_json(entry.definition)
    return build_mission_package(definition).to_json()


def prepare_execution(
    entry: LibraryEntry,
    package: JSONObject,
    gateway: MissionExecutionGateway,
    trigger: ExecutionTrigger,
    schedule_id: Optional[str] = None,
    start_now: bool = True,
) -> tuple[ExecutionRecord, JSONObject]:
    """
    Hand a Mission Package to the Digital Twin and open a history record.

    With ``start_now`` the operator's START intent follows the transfer; with
    ``start_now=False`` the package is deployed and the runtime waits, exactly
    as after a Mission Review deployment.
    """
    payload = gateway.get_mission_payload()
    status = _status_of(payload)
    if status in BUSY_RUNTIME_STATES:
        raise ExecutionConflict(
            f"The Digital Twin is currently {status.lower()}. Stop the running "
            "mission in Mission Control before executing another one."
        )

    receipt = gateway.deploy_mission_package(dict(package))
    record = execution_from_package(entry, package, trigger, schedule_id)
    deployment_id = receipt.get("deployment_id")
    record.deployment_id = deployment_id if isinstance(deployment_id, str) else None

    if start_now and not gateway.start_mission():
        raise ExecutionConflict(
            "The Digital Twin did not accept the start intent; the package is "
            "deployed and can be started from Mission Control."
        )
    apply_runtime_state(record, gateway.get_mission_payload())
    return record, receipt


def dispatch_due_schedules(
    schedules: list[ScheduleEntry],
    resolve_entry: Callable[[str], Optional[LibraryEntry]],
    gateway: MissionExecutionGateway,
    now_ms: Optional[int] = None,
) -> list[tuple[ScheduleEntry, Optional[ExecutionRecord]]]:
    """
    Run the occurrences the operator scheduled and that are now due.

    Only enabled schedules are considered, each due occurrence is dispatched
    once, and a conflict is recorded on the schedule as ``last_result`` rather
    than resolved: nothing is queued, retried, moved or reassigned.
    """
    moment = now_ms if now_ms is not None else int(time.time() * 1000)
    results: list[tuple[ScheduleEntry, Optional[ExecutionRecord]]] = []

    for schedule in schedules:
        occurrence_ms = due_occurrence(schedule, moment)
        if occurrence_ms is None:
            continue
        schedule.last_triggered_ms = occurrence_ms
        schedule.updated_ms = moment

        entry = resolve_entry(schedule.entry_id)
        if entry is None:
            schedule.last_result = (
                f"saved mission '{schedule.entry_id}' no longer exists"
            )
            results.append((schedule, None))
            continue
        try:
            record, _ = prepare_execution(
                entry,
                resolve_package(entry),
                gateway,
                ExecutionTrigger.SCHEDULED,
                schedule_id=schedule.schedule_id,
            )
        except ExecutionError as exc:
            schedule.last_result = str(exc)
            results.append((schedule, None))
            continue
        schedule.last_result = f"executed ({record.execution_id})"
        results.append((schedule, record))

    return results


def _status_of(payload: JSONObject) -> str:
    value = payload.get("status")
    return value.upper() if isinstance(value, str) else ""
