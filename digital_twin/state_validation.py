"""
Phase 10B — State Validation.

Validates incoming state updates before they are applied to the Digital Twin.
Rejects invalid updates. No decision-making — only consistency checks.

Validates:
- Duplicate drone IDs
- Invalid timestamps
- Inconsistent swarm state
- Missing required fields
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from digital_twin.state_models import (
    DroneState,
    DroneStateUpdate,
    SwarmState,
    SwarmStateUpdate,
)

logger = logging.getLogger("eea.digital_twin.validation")


class ValidationError(Enum):
    """Categories of validation failures."""
    DUPLICATE_DRONE_ID = "duplicate_drone_id"
    INVALID_TIMESTAMP = "invalid_timestamp"
    TIMESTAMP_REGRESSION = "timestamp_regression"
    INCONSISTENT_STATE = "inconsistent_state"
    MISSING_DRONE_ID = "missing_drone_id"
    INVALID_BATTERY = "invalid_battery"
    INVALID_GPS_ACCURACY = "invalid_gps_accuracy"
    DRONE_COUNT_MISMATCH = "drone_count_mismatch"


@dataclass(frozen=True)
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    errors: tuple[ValidationError, ...] = ()
    details: tuple[str, ...] = ()


class StateValidator:
    """
    Validates state updates before application to Digital Twin.

    Pure validation — no state modification, no decision logic.
    """

    def validate_drone_update(
        self,
        update: DroneStateUpdate,
        current_state: Optional[DroneState] = None,
    ) -> ValidationResult:
        """Validate an incoming drone state update."""
        errors: list[ValidationError] = []
        details: list[str] = []

        # Check drone_id
        if update.drone_id <= 0:
            errors.append(ValidationError.MISSING_DRONE_ID)
            details.append(f"Invalid drone_id: {update.drone_id}")

        # Check timestamp
        if update.timestamp_ms < 0:
            errors.append(ValidationError.INVALID_TIMESTAMP)
            details.append(f"Negative timestamp: {update.timestamp_ms}")

        # Check timestamp regression (shouldn't go backwards)
        if current_state and update.timestamp_ms < current_state.last_update_ms:
            errors.append(ValidationError.TIMESTAMP_REGRESSION)
            details.append(
                f"Timestamp regression: {update.timestamp_ms} < "
                f"{current_state.last_update_ms}"
            )

        # Check battery range
        if not (0.0 <= update.battery_pct <= 100.0):
            errors.append(ValidationError.INVALID_BATTERY)
            details.append(f"Battery out of range: {update.battery_pct}%")

        # Check GPS accuracy
        if update.gps_accuracy_m < 0.0:
            errors.append(ValidationError.INVALID_GPS_ACCURACY)
            details.append(f"Negative GPS accuracy: {update.gps_accuracy_m}")

        if errors:
            logger.warning(
                "StateValidator: drone %d update rejected (%d errors)",
                update.drone_id, len(errors),
            )
            return ValidationResult(
                valid=False,
                errors=tuple(errors),
                details=tuple(details),
            )

        return ValidationResult(valid=True)

    def validate_swarm_update(
        self,
        update: SwarmStateUpdate,
        current_state: Optional[SwarmState] = None,
    ) -> ValidationResult:
        """Validate an incoming swarm state update."""
        errors: list[ValidationError] = []
        details: list[str] = []

        # Check timestamp
        if update.timestamp_ms < 0:
            errors.append(ValidationError.INVALID_TIMESTAMP)
            details.append(f"Negative timestamp: {update.timestamp_ms}")

        # Check count consistency
        if update.active_count + update.fail_count > update.total_drones:
            errors.append(ValidationError.INCONSISTENT_STATE)
            details.append(
                f"active({update.active_count}) + fail({update.fail_count}) > "
                f"total({update.total_drones})"
            )

        # Check for duplicate drone IDs in active list
        if len(set(update.active_drone_ids)) != len(update.active_drone_ids):
            errors.append(ValidationError.DUPLICATE_DRONE_ID)
            details.append("Duplicate drone IDs in active list")

        if errors:
            logger.warning(
                "StateValidator: swarm update rejected (%d errors)",
                len(errors),
            )
            return ValidationResult(
                valid=False,
                errors=tuple(errors),
                details=tuple(details),
            )

        return ValidationResult(valid=True)

    def validate_swarm_state_consistency(
        self, state: SwarmState,
    ) -> ValidationResult:
        """Validate internal consistency of a complete SwarmState."""
        errors: list[ValidationError] = []
        details: list[str] = []

        # Check for duplicate drone IDs
        drone_ids = [d.drone_id for d in state.drone_states]
        if len(set(drone_ids)) != len(drone_ids):
            errors.append(ValidationError.DUPLICATE_DRONE_ID)
            duplicates = [
                d for d in drone_ids if drone_ids.count(d) > 1
            ]
            details.append(f"Duplicate drone IDs: {set(duplicates)}")

        # Check drone count consistency
        if state.total_drones != len(state.drone_states):
            errors.append(ValidationError.DRONE_COUNT_MISMATCH)
            details.append(
                f"total_drones({state.total_drones}) != "
                f"drone_states count({len(state.drone_states)})"
            )

        # Check timestamp validity
        if state.timestamp_ms < 0:
            errors.append(ValidationError.INVALID_TIMESTAMP)
            details.append(f"Negative swarm timestamp: {state.timestamp_ms}")

        if errors:
            return ValidationResult(
                valid=False,
                errors=tuple(errors),
                details=tuple(details),
            )

        return ValidationResult(valid=True)
