"""
Hive Integration Layer (Phase 8.5)

Integrates all Phase 8.1-8.4 systems into a single unified orchestration
framework. This module provides a single entry point for the entire Hive
system while preserving strict separation of responsibilities.

This is an integration layer ONLY -- it does NOT introduce:
- scheduling logic
- optimization logic
- fleet/resource balancing
- assignment or allocation logic
- prioritization logic
- recommendation logic
- decision-making of any kind

The Integration Layer may:
- observe state
- aggregate state
- expose state
- coordinate component communication
- manage component lifecycles

It may NOT decide anything.

Components:
- HiveRuntime: manages lifecycle of all Hive sub-systems
- HiveController: unified orchestration entry point
- HiveSystemSnapshot: consolidated system-wide state

See docs/architecture/phase8_design.md (Phase 8.5) for design spec.
See docs/architecture/decision_boundary_map_phase8.md for boundaries.
"""

from dataclasses import dataclass
from typing import Optional

from core.hive import (
    FleetRegistry,
    MissionQueue,
    QueuedMission,
    MissionPriority,
    HiveState,
    build_hive_state,
)
from core.mission_orchestrator import (
    MissionLifecycleManager,
    MissionExecutionContext,
    MissionResult,
    run_mission,
    run_queue,
)
from core.fleet_manager import (
    DroneStatusTracker,
    DroneAllocationManager,
    FleetStateUpdater,
)
from core.resource_system import (
    BatteryInventoryManager,
    LiquidInventoryManager,
    ResourceStateTracker,
    ResourceSnapshot,
)
from utils.logger import get_logger

logger = get_logger("hive_integration")


# =========================================================================
# Hive Runtime
# =========================================================================

class HiveRuntime:
    """
    Manages lifecycle of all Hive sub-systems.

    Initializes and holds references to all Phase 8.1-8.4 components.
    Provides access to individual sub-systems for direct interaction
    when needed. Does NOT add any logic on top of sub-systems.
    """

    def __init__(self) -> None:
        # Phase 8.1 -- Hive Core Foundation
        self.fleet = FleetRegistry()
        self.queue = MissionQueue()

        # Phase 8.2 -- Mission Orchestrator
        self.lifecycle = MissionLifecycleManager()

        # Phase 8.3 -- Fleet Manager
        self.status_tracker = DroneStatusTracker(self.fleet)
        self.allocator = DroneAllocationManager(self.fleet)
        self.fleet_updater = FleetStateUpdater(
            self.fleet, self.status_tracker, self.allocator,
        )

        # Phase 8.4 -- Resource System
        self.batteries = BatteryInventoryManager()
        self.liquids = LiquidInventoryManager()
        self.resources = ResourceStateTracker(
            self.fleet, self.batteries, self.liquids,
        )

        logger.info("HiveRuntime: initialized all sub-systems")

    def hive_state(self) -> HiveState:
        """Build a current HiveState snapshot (Phase 8.1)."""
        return build_hive_state(self.fleet, self.queue)

    def resource_snapshot(self) -> ResourceSnapshot:
        """Build a current ResourceSnapshot (Phase 8.4)."""
        return self.resources.build_snapshot()


# =========================================================================
# Hive System Snapshot
# =========================================================================

@dataclass
class HiveSystemSnapshot:
    """
    Consolidated system-wide state snapshot.

    Aggregates HiveState, fleet assignment summary, and resource
    snapshot into a single read-only view. No decision-making --
    purely a state aggregation.
    """
    hive_state: HiveState
    fleet_summary: dict
    resource_snapshot: ResourceSnapshot
    lifecycle_summary: dict


# =========================================================================
# Hive Controller
# =========================================================================

class HiveController:
    """
    Unified orchestration entry point for the Hive system.

    Provides high-level operations that coordinate between sub-systems.
    All operations delegate to existing Phase 8.1-8.4 components.
    No new intelligence, no decision-making -- integration only.
    """

    def __init__(self, runtime: Optional[HiveRuntime] = None) -> None:
        self._runtime = runtime if runtime is not None else HiveRuntime()

    @property
    def runtime(self) -> HiveRuntime:
        """Access the underlying HiveRuntime for direct sub-system interaction."""
        return self._runtime

    # -----------------------------------------------------------------
    # Fleet setup (delegates to Phase 8.1 FleetRegistry)
    # -----------------------------------------------------------------

    def register_drone(self, drone_id: int) -> None:
        """Register a drone in the fleet."""
        self._runtime.fleet.register_drone(drone_id)
        logger.info("HiveController: drone %d registered", drone_id)

    def register_drones(self, drone_ids: list[int]) -> None:
        """Register multiple drones in the fleet."""
        for drone_id in drone_ids:
            self._runtime.fleet.register_drone(drone_id)
        logger.info(
            "HiveController: %d drones registered", len(drone_ids),
        )

    # -----------------------------------------------------------------
    # Resource setup (delegates to Phase 8.4)
    # -----------------------------------------------------------------

    def register_battery(self, battery_id: int, charge_pct: float = 100.0) -> None:
        """Register a battery in the inventory."""
        self._runtime.batteries.register_battery(battery_id, charge_pct)

    def register_reservoir(self, reservoir_id: int, capacity_l: float) -> None:
        """Register a liquid reservoir in the inventory."""
        self._runtime.liquids.register_reservoir(reservoir_id, capacity_l)

    # -----------------------------------------------------------------
    # Mission management (delegates to Phase 8.1 MissionQueue)
    # -----------------------------------------------------------------

    def submit_mission(
        self,
        mission_id: str,
        field_size_ha: float,
        crop_type: str,
        num_drones: int,
        priority: MissionPriority = MissionPriority.NORMAL,
        wind_speed_kmh: float = 10.0,
        temperature_c: float = 25.0,
    ) -> QueuedMission:
        """
        Submit a mission to the Hive queue.

        Creates a QueuedMission and enqueues it. No execution occurs
        until execute_next() or execute_all() is called.
        """
        mission = QueuedMission(
            mission_id=mission_id,
            field_size_ha=field_size_ha,
            crop_type=crop_type,
            num_drones=num_drones,
            priority=priority,
            wind_speed_kmh=wind_speed_kmh,
            temperature_c=temperature_c,
        )
        self._runtime.queue.enqueue(mission)
        logger.info(
            "HiveController: mission '%s' submitted (priority=%s)",
            mission_id, priority.name,
        )
        return mission

    # -----------------------------------------------------------------
    # Mission execution (delegates to Phase 8.2)
    # -----------------------------------------------------------------

    def execute_next(self) -> Optional[MissionResult]:
        """
        Execute the next queued mission through the Phase 0-7 pipeline.

        Dequeues the highest-priority mission and runs it in an isolated
        context. Returns None if no missions are queued.
        """
        queued = self._runtime.queue.dequeue()
        if queued is None:
            logger.info("HiveController: no missions to execute")
            return None

        result = run_mission(queued, self._runtime.lifecycle)

        if result.success:
            self._runtime.queue.complete(queued.mission_id)
        else:
            self._runtime.queue.fail(queued.mission_id)

        logger.info(
            "HiveController: mission '%s' executed — success=%s",
            queued.mission_id, result.success,
        )
        return result

    def execute_all(self) -> list[MissionResult]:
        """
        Execute all queued missions sequentially.

        Delegates to run_queue() which processes the entire queue
        in priority order with isolated contexts per mission.
        """
        results = run_queue(self._runtime.queue, self._runtime.lifecycle)
        logger.info(
            "HiveController: executed %d missions (%d succeeded, %d failed)",
            len(results),
            sum(1 for r in results if r.success),
            sum(1 for r in results if not r.success),
        )
        return results

    # -----------------------------------------------------------------
    # State visibility (aggregation only, no decisions)
    # -----------------------------------------------------------------

    def system_snapshot(self) -> HiveSystemSnapshot:
        """
        Build a consolidated system-wide state snapshot.

        Aggregates state from all Phase 8.1-8.4 sub-systems into
        a single read-only view. No decision-making -- purely state.
        """
        hive_state = self._runtime.hive_state()
        fleet_summary = self._runtime.fleet_updater.fleet_assignment_summary()
        resource_snapshot = self._runtime.resource_snapshot()

        lifecycle_summary = {
            "total_contexts": self._runtime.lifecycle.total_count,
            "completed": self._runtime.lifecycle.completed_count,
            "failed": self._runtime.lifecycle.failed_count,
        }

        snapshot = HiveSystemSnapshot(
            hive_state=hive_state,
            fleet_summary=fleet_summary,
            resource_snapshot=resource_snapshot,
            lifecycle_summary=lifecycle_summary,
        )

        logger.info(
            "HiveController: system snapshot — fleet=%d, queued=%d, "
            "batteries=%d, reservoirs=%d",
            hive_state.fleet_size,
            hive_state.missions_queued,
            resource_snapshot.total_available_batteries,
            resource_snapshot.total_available_reservoirs,
        )
        return snapshot

    def get_mission_context(self, mission_id: str) -> MissionExecutionContext:
        """Get the execution context for a specific mission."""
        return self._runtime.lifecycle.get_context(mission_id)

    def get_mission_resources(self, mission_id: str) -> dict:
        """Get resource consumption summary for a specific mission."""
        return self._runtime.resources.get_mission_consumption(mission_id)
