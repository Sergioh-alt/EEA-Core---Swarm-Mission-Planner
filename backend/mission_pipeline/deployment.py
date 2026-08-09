"""
Mission Definition Pipeline — Mission Review & Deployment (Phase 10D.6).

Models the operational gateway between planning and execution:

    Mission Package -> operator review + checklist -> deployment -> Digital Twin

Boundary:
    * No planning, optimization, allocation, scheduling or routing happens here.
      The Mission Package is produced by the Planning Core and transferred
      byte-for-byte; deployment never generates or modifies routes.
    * This module imports no runtime modules (Hive / HAL / PX4 / MAVLink / ROS2
      / Simulation Core). The Digital Twin is reached exclusively through the
      narrow ``TwinDeploymentGateway`` protocol implemented by the runtime.
    * Deployment does not start execution. Mission lifecycle stays with the
      operator intents already owned by Mission Control.

Extensibility: the operator checklist is a data-driven list of ``ChecklistItem``
rather than fixed booleans, so later enterprise gates (weather integration,
regulatory validation, digital signatures, operator permissions, maintenance
status, ...) can be added without touching the state machine or the API.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional, Protocol

from backend.serializers import JSONObject, JSONValue


class DeploymentError(RuntimeError):
    """Raised when a deployment transition is not allowed."""


class DeploymentState(str, Enum):
    """
    Lifecycle of a mission from draft to archive.

    Mission Review owns the transitions up to and including ``DEPLOYED``.
    ``EXECUTING`` onward belong to Mission Control and the Digital Twin and are
    represented here only so the operator can see the whole progression.
    """

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


#: States in which the Mission Definition and its package are immutable.
LOCKED_STATES = frozenset(
    {
        DeploymentState.DEPLOYED,
        DeploymentState.EXECUTING,
        DeploymentState.COMPLETED,
        DeploymentState.ARCHIVED,
    }
)

#: The default operator confirmation gate. Data-driven so it can be extended.
DEFAULT_CHECKLIST: tuple[tuple[str, str], ...] = (
    ("weather_verified", "Weather verified"),
    ("area_inspected", "Area inspected"),
    ("products_loaded", "Products loaded"),
    ("fleet_prepared", "Fleet prepared"),
    ("batteries_charged", "Batteries charged"),
    ("parameters_verified", "Mission parameters verified"),
    ("safety_perimeter", "Safety perimeter confirmed"),
)


@dataclass
class ChecklistItem:
    """
    A single operator confirmation.

    Confirmation is an assertion by the operator; it never alters the Mission
    Package or any Planning Core output.
    """

    item_id: str
    label: str
    confirmed: bool = False
    required: bool = True


def default_checklist() -> list[ChecklistItem]:
    return [ChecklistItem(item_id=i, label=lab) for i, lab in DEFAULT_CHECKLIST]


@dataclass
class DeploymentRecord:
    """
    Review/deployment state for one Mission Definition.

    ``package`` is populated only at deployment: it is the immutable snapshot of
    the Mission Package that was handed to the Digital Twin, retained for
    traceability. Before deployment the review screen reads a freshly computed
    package from the Planning Core.
    """

    mission_id: str
    state: DeploymentState = DeploymentState.DRAFT
    checklist: list[ChecklistItem] = field(default_factory=default_checklist)
    package: Optional[JSONObject] = None
    definition_version: Optional[int] = None
    deployment_id: Optional[str] = None
    deployed_ms: Optional[int] = None
    updated_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    # -- gating ---------------------------------------------------------

    @property
    def checklist_complete(self) -> bool:
        return all(item.confirmed for item in self.checklist if item.required)

    @property
    def is_locked(self) -> bool:
        """Deployed missions are immutable — create a new definition instead."""
        return self.state in LOCKED_STATES

    def confirm(self, confirmations: dict[str, bool]) -> None:
        """
        Apply operator confirmations and re-derive the pre-deployment state.

        Raises if the mission is already deployed: a deployed package is locked.
        """
        if self.is_locked:
            raise DeploymentError(
                "Mission is deployed and locked; create a new Mission "
                "Definition to change anything."
            )
        for item in self.checklist:
            if item.item_id in confirmations:
                item.confirmed = bool(confirmations[item.item_id])
        self._refresh_state()

    def _refresh_state(self) -> None:
        """
        Derive Draft / Ready for Review / Approved from operator progress.

        Deployment states are set explicitly by ``mark_deployed`` and are never
        recomputed here.
        """
        if self.is_locked or self.state == DeploymentState.DEPLOYING:
            return
        if self.checklist_complete:
            self.state = DeploymentState.APPROVED
        elif any(item.confirmed for item in self.checklist):
            self.state = DeploymentState.READY_FOR_REVIEW
        else:
            self.state = DeploymentState.DRAFT
        self.updated_ms = int(time.time() * 1000)

    def mark_deployed(
        self,
        package: JSONObject,
        deployment_id: str,
        definition_version: Optional[int] = None,
    ) -> None:
        """Lock the record around the exact package handed to the Digital Twin."""
        self.package = dict(package)
        self.deployment_id = deployment_id
        self.definition_version = definition_version
        self.state = DeploymentState.DEPLOYED
        self.deployed_ms = int(time.time() * 1000)
        self.updated_ms = self.deployed_ms

    # -- (de)serialization ----------------------------------------------

    def to_json(self) -> JSONObject:
        return {
            "mission_id": self.mission_id,
            "state": self.state.value,
            "checklist": [
                {
                    "item_id": i.item_id,
                    "label": i.label,
                    "confirmed": i.confirmed,
                    "required": i.required,
                }
                for i in self.checklist
            ],
            "checklist_complete": self.checklist_complete,
            "locked": self.is_locked,
            "package": self.package,
            "definition_version": self.definition_version,
            "deployment_id": self.deployment_id,
            "deployed_ms": self.deployed_ms,
            "updated_ms": self.updated_ms,
        }

    @classmethod
    def from_json(cls, data: JSONObject) -> "DeploymentRecord":
        raw_items = data.get("checklist")
        items: list[ChecklistItem] = []
        if isinstance(raw_items, list):
            for entry in raw_items:
                if not isinstance(entry, dict):
                    continue
                item_id = entry.get("item_id")
                if not isinstance(item_id, str):
                    continue
                label = entry.get("label")
                items.append(
                    ChecklistItem(
                        item_id=item_id,
                        label=label if isinstance(label, str) else item_id,
                        confirmed=bool(entry.get("confirmed", False)),
                        required=bool(entry.get("required", True)),
                    )
                )
        record = cls(
            mission_id=_as_str(data.get("mission_id"), ""),
            state=_state_from(data.get("state")),
            checklist=items or default_checklist(),
            package=_as_opt_object(data.get("package")),
            definition_version=_as_opt_int(data.get("definition_version")),
            deployment_id=_as_opt_str(data.get("deployment_id")),
            deployed_ms=_as_opt_int(data.get("deployed_ms")),
        )
        updated = _as_opt_int(data.get("updated_ms"))
        if updated is not None:
            record.updated_ms = updated
        return record


class TwinDeploymentGateway(Protocol):
    """
    The single channel through which an approved package reaches the runtime.

    Implemented by the Digital Twin runtime layer. Keeping it a Protocol lets
    the pipeline stay free of runtime imports while deployment remains the only
    planning-to-execution transition.
    """

    def deploy_mission_package(self, package: JSONObject) -> JSONObject:
        ...


def deploy_mission(
    record: DeploymentRecord,
    package: JSONObject,
    gateway: TwinDeploymentGateway,
    definition_version: Optional[int] = None,
) -> tuple[DeploymentRecord, JSONObject]:
    """
    Authorize and perform deployment: transfer the package to the Digital Twin.

    The package is passed through unchanged — no routes are generated or
    modified, no drones assigned, no resources rebalanced, no timing optimized.
    Execution is not started; that stays with Mission Control.
    """
    if record.is_locked:
        raise DeploymentError(
            "Mission is already deployed; its package is locked. Create a new "
            "Mission Definition to deploy again."
        )
    if not record.checklist_complete:
        missing = [i.label for i in record.checklist if i.required and not i.confirmed]
        raise DeploymentError(
            "Operational checklist incomplete: " + ", ".join(missing)
        )

    record.state = DeploymentState.DEPLOYING
    # Deploy an immutable copy so no later mutation can reach the runtime.
    frozen = dict(package)
    receipt = gateway.deploy_mission_package(frozen)
    deployment_id = _receipt_id(receipt)
    record.mark_deployed(frozen, deployment_id, definition_version)
    return record, receipt


def _receipt_id(receipt: JSONObject) -> str:
    value = receipt.get("deployment_id")
    if isinstance(value, str) and value:
        return value
    return f"deploy_{uuid.uuid4().hex[:12]}"


def new_record(mission_id: str) -> DeploymentRecord:
    """A fresh Draft record for a mission that has never been reviewed."""
    return DeploymentRecord(mission_id=mission_id)


def with_mission_id(record: DeploymentRecord, mission_id: str) -> DeploymentRecord:
    return replace(record, mission_id=mission_id)


# ---------------------------------------------------------------------------
# Typed coercion helpers (no Any / getattr)
# ---------------------------------------------------------------------------


def _state_from(value: JSONValue) -> DeploymentState:
    if isinstance(value, str):
        try:
            return DeploymentState(value)
        except ValueError:
            return DeploymentState.DRAFT
    return DeploymentState.DRAFT


def _as_str(value: JSONValue, default: str) -> str:
    return value if isinstance(value, str) else default


def _as_opt_str(value: JSONValue) -> Optional[str]:
    return value if isinstance(value, str) else None


def _as_opt_int(value: JSONValue) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_opt_object(value: JSONValue) -> Optional[JSONObject]:
    return value if isinstance(value, dict) else None
