"""
Resource System (Phase 8.4)

Fleet-wide resource awareness and tracking across missions.
This module manages resource visibility only — it does NOT perform:
- resource scheduling
- charging/refill optimization
- battery/liquid allocation logic
- resource balancing across missions
- mission or drone prioritization
- automatic reassignment
- decision-making of any kind

Components:
- BatteryUnit: individual battery state representation
- BatteryInventoryManager: fleet battery pool tracking
- LiquidReservoir: individual liquid reservoir state representation
- LiquidInventoryManager: fleet liquid supply tracking
- ResourceStateTracker: unified resource state tracking per drone
- ResourceSnapshot: immutable resource state snapshot

See docs/architecture/phase8_design.md (Phase 8.4) for design spec.
See docs/architecture/decision_boundary_map_phase8.md for boundaries.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.hive import FleetRegistry
from utils.logger import get_logger

logger = get_logger("resource_system")


# =========================================================================
# Battery Inventory
# =========================================================================

class BatteryState(Enum):
    """Battery lifecycle states."""
    AVAILABLE = "available"
    IN_USE = "in_use"
    CHARGING = "charging"
    DEPLETED = "depleted"


@dataclass
class BatteryUnit:
    """An individual battery in the inventory."""
    battery_id: int
    charge_pct: float = 100.0
    state: BatteryState = BatteryState.AVAILABLE
    assigned_drone_id: Optional[int] = None
    cycle_count: int = 0


@dataclass
class BatteryConsumptionRecord:
    """Record of battery consumption for a drone during a mission."""
    battery_id: int
    drone_id: int
    mission_id: str
    start_pct: float
    end_pct: float
    consumed_pct: float


class BatteryInventoryManager:
    """
    Fleet battery pool tracking.

    Tracks battery availability, usage state, and charging state
    across the fleet. Does NOT decide which drone or mission gets
    which battery — purely records and reports state.
    """

    def __init__(self) -> None:
        self._batteries: dict[int, BatteryUnit] = {}
        self._consumption_log: list[BatteryConsumptionRecord] = []

    def register_battery(self, battery_id: int, charge_pct: float = 100.0) -> BatteryUnit:
        """Register a new battery in the inventory."""
        if battery_id in self._batteries:
            raise ValueError(f"Battery {battery_id} already registered")
        battery = BatteryUnit(battery_id=battery_id, charge_pct=charge_pct)
        self._batteries[battery_id] = battery
        logger.info("BatteryInventory: battery %d registered (%.1f%%)", battery_id, charge_pct)
        return battery

    def get_battery(self, battery_id: int) -> BatteryUnit:
        """Get a battery by ID."""
        if battery_id not in self._batteries:
            raise ValueError(f"Battery {battery_id} not in inventory")
        return self._batteries[battery_id]

    def assign_to_drone(self, battery_id: int, drone_id: int) -> BatteryUnit:
        """
        Record a battery assignment to a drone.

        Validates battery is AVAILABLE. Caller decides the assignment.
        """
        battery = self.get_battery(battery_id)
        if battery.state != BatteryState.AVAILABLE:
            raise ValueError(
                f"Battery {battery_id} is not available "
                f"(current state: {battery.state.value})"
            )
        battery.state = BatteryState.IN_USE
        battery.assigned_drone_id = drone_id
        logger.info(
            "BatteryInventory: battery %d assigned to drone %d",
            battery_id, drone_id,
        )
        return battery

    def record_consumption(
        self,
        battery_id: int,
        drone_id: int,
        mission_id: str,
        consumed_pct: float,
    ) -> BatteryConsumptionRecord:
        """
        Record battery consumption during a mission.

        Updates charge level and logs the consumption event.
        """
        battery = self.get_battery(battery_id)
        start_pct = battery.charge_pct
        battery.charge_pct = max(0.0, battery.charge_pct - consumed_pct)
        end_pct = battery.charge_pct

        if battery.charge_pct <= 0.0:
            battery.state = BatteryState.DEPLETED

        record = BatteryConsumptionRecord(
            battery_id=battery_id,
            drone_id=drone_id,
            mission_id=mission_id,
            start_pct=round(start_pct, 1),
            end_pct=round(end_pct, 1),
            consumed_pct=round(consumed_pct, 1),
        )
        self._consumption_log.append(record)

        logger.info(
            "BatteryInventory: battery %d consumed %.1f%% (%.1f%% → %.1f%%)",
            battery_id, consumed_pct, start_pct, end_pct,
        )
        return record

    def release_from_drone(self, battery_id: int) -> BatteryUnit:
        """Release a battery from a drone (returns to AVAILABLE or DEPLETED)."""
        battery = self.get_battery(battery_id)
        if battery.state == BatteryState.IN_USE:
            battery.state = (
                BatteryState.DEPLETED if battery.charge_pct <= 0.0
                else BatteryState.AVAILABLE
            )
        battery.assigned_drone_id = None
        battery.cycle_count += 1
        logger.info(
            "BatteryInventory: battery %d released (state=%s, charge=%.1f%%)",
            battery_id, battery.state.value, battery.charge_pct,
        )
        return battery

    def set_charging(self, battery_id: int) -> BatteryUnit:
        """Set a battery to CHARGING state."""
        battery = self.get_battery(battery_id)
        if battery.state == BatteryState.IN_USE:
            raise ValueError(
                f"Battery {battery_id} is in use — release before charging"
            )
        battery.state = BatteryState.CHARGING
        logger.info("BatteryInventory: battery %d set to charging", battery_id)
        return battery

    def complete_charging(self, battery_id: int, charge_pct: float = 100.0) -> BatteryUnit:
        """Mark charging complete — battery returns to AVAILABLE."""
        battery = self.get_battery(battery_id)
        if battery.state != BatteryState.CHARGING:
            raise ValueError(
                f"Battery {battery_id} is not charging "
                f"(current state: {battery.state.value})"
            )
        battery.charge_pct = charge_pct
        battery.state = BatteryState.AVAILABLE
        logger.info(
            "BatteryInventory: battery %d charged to %.1f%%",
            battery_id, charge_pct,
        )
        return battery

    def get_by_state(self, state: BatteryState) -> list[BatteryUnit]:
        """Return all batteries in the given state."""
        return [b for b in self._batteries.values() if b.state == state]

    def get_available(self) -> list[BatteryUnit]:
        """Return all AVAILABLE batteries."""
        return self.get_by_state(BatteryState.AVAILABLE)

    def get_consumption_log(
        self, mission_id: Optional[str] = None
    ) -> list[BatteryConsumptionRecord]:
        """Return consumption log, optionally filtered by mission."""
        if mission_id is not None:
            return [r for r in self._consumption_log if r.mission_id == mission_id]
        return list(self._consumption_log)

    def inventory_summary(self) -> dict:
        """Return a read-only summary of battery inventory state."""
        total = len(self._batteries)
        avg_charge = (
            sum(b.charge_pct for b in self._batteries.values()) / total
            if total > 0
            else 0.0
        )
        return {
            "total_batteries": total,
            "by_state": {
                state.value: len(self.get_by_state(state))
                for state in BatteryState
            },
            "avg_charge_pct": round(avg_charge, 1),
            "total_consumption_events": len(self._consumption_log),
        }


# =========================================================================
# Liquid Inventory
# =========================================================================

class ReservoirState(Enum):
    """Liquid reservoir lifecycle states."""
    FULL = "full"
    PARTIAL = "partial"
    EMPTY = "empty"
    REFILLING = "refilling"


@dataclass
class LiquidReservoir:
    """An individual liquid reservoir (tank/supply) in the inventory."""
    reservoir_id: int
    capacity_l: float
    current_level_l: float
    state: ReservoirState = ReservoirState.FULL
    assigned_drone_id: Optional[int] = None


@dataclass
class LiquidConsumptionRecord:
    """Record of liquid consumption for a drone during a mission."""
    reservoir_id: int
    drone_id: int
    mission_id: str
    start_level_l: float
    end_level_l: float
    consumed_l: float


class LiquidInventoryManager:
    """
    Fleet liquid supply tracking.

    Tracks liquid reservoir levels, refill state, and consumption
    across the fleet. Does NOT decide which drone or mission receives
    liquid — purely records and reports state.
    """

    def __init__(self) -> None:
        self._reservoirs: dict[int, LiquidReservoir] = {}
        self._consumption_log: list[LiquidConsumptionRecord] = []

    def register_reservoir(
        self, reservoir_id: int, capacity_l: float, current_level_l: Optional[float] = None,
    ) -> LiquidReservoir:
        """Register a new liquid reservoir."""
        if reservoir_id in self._reservoirs:
            raise ValueError(f"Reservoir {reservoir_id} already registered")
        level = current_level_l if current_level_l is not None else capacity_l
        reservoir = LiquidReservoir(
            reservoir_id=reservoir_id,
            capacity_l=capacity_l,
            current_level_l=level,
        )
        self._reservoirs[reservoir_id] = reservoir
        logger.info(
            "LiquidInventory: reservoir %d registered (%.1f/%.1f L)",
            reservoir_id, level, capacity_l,
        )
        return reservoir

    def get_reservoir(self, reservoir_id: int) -> LiquidReservoir:
        """Get a reservoir by ID."""
        if reservoir_id not in self._reservoirs:
            raise ValueError(f"Reservoir {reservoir_id} not in inventory")
        return self._reservoirs[reservoir_id]

    def assign_to_drone(self, reservoir_id: int, drone_id: int) -> LiquidReservoir:
        """
        Record a reservoir assignment to a drone.

        Only FULL or PARTIAL reservoirs can be assigned. Caller decides.
        """
        reservoir = self.get_reservoir(reservoir_id)
        if reservoir.state in (ReservoirState.EMPTY, ReservoirState.REFILLING):
            raise ValueError(
                f"Reservoir {reservoir_id} is not available "
                f"(current state: {reservoir.state.value})"
            )
        reservoir.assigned_drone_id = drone_id
        logger.info(
            "LiquidInventory: reservoir %d assigned to drone %d",
            reservoir_id, drone_id,
        )
        return reservoir

    def record_consumption(
        self,
        reservoir_id: int,
        drone_id: int,
        mission_id: str,
        consumed_l: float,
    ) -> LiquidConsumptionRecord:
        """
        Record liquid consumption during a mission.

        Updates reservoir level and logs the consumption event.
        """
        reservoir = self.get_reservoir(reservoir_id)
        start_level = reservoir.current_level_l
        reservoir.current_level_l = max(0.0, reservoir.current_level_l - consumed_l)
        end_level = reservoir.current_level_l

        if reservoir.current_level_l <= 0.0:
            reservoir.state = ReservoirState.EMPTY
        elif reservoir.current_level_l < reservoir.capacity_l:
            reservoir.state = ReservoirState.PARTIAL

        record = LiquidConsumptionRecord(
            reservoir_id=reservoir_id,
            drone_id=drone_id,
            mission_id=mission_id,
            start_level_l=round(start_level, 1),
            end_level_l=round(end_level, 1),
            consumed_l=round(consumed_l, 1),
        )
        self._consumption_log.append(record)

        logger.info(
            "LiquidInventory: reservoir %d consumed %.1f L (%.1f → %.1f L)",
            reservoir_id, consumed_l, start_level, end_level,
        )
        return record

    def release_from_drone(self, reservoir_id: int) -> LiquidReservoir:
        """Release a reservoir from a drone."""
        reservoir = self.get_reservoir(reservoir_id)
        reservoir.assigned_drone_id = None
        logger.info(
            "LiquidInventory: reservoir %d released (state=%s, level=%.1f L)",
            reservoir_id, reservoir.state.value, reservoir.current_level_l,
        )
        return reservoir

    def set_refilling(self, reservoir_id: int) -> LiquidReservoir:
        """Set a reservoir to REFILLING state."""
        reservoir = self.get_reservoir(reservoir_id)
        if reservoir.assigned_drone_id is not None:
            raise ValueError(
                f"Reservoir {reservoir_id} is assigned to drone "
                f"{reservoir.assigned_drone_id} — release before refilling"
            )
        reservoir.state = ReservoirState.REFILLING
        logger.info("LiquidInventory: reservoir %d set to refilling", reservoir_id)
        return reservoir

    def complete_refill(self, reservoir_id: int, fill_level_l: Optional[float] = None) -> LiquidReservoir:
        """Mark refill complete — reservoir returns to FULL or PARTIAL."""
        reservoir = self.get_reservoir(reservoir_id)
        if reservoir.state != ReservoirState.REFILLING:
            raise ValueError(
                f"Reservoir {reservoir_id} is not refilling "
                f"(current state: {reservoir.state.value})"
            )
        level = fill_level_l if fill_level_l is not None else reservoir.capacity_l
        reservoir.current_level_l = level
        reservoir.state = (
            ReservoirState.FULL if level >= reservoir.capacity_l
            else ReservoirState.PARTIAL
        )
        logger.info(
            "LiquidInventory: reservoir %d refilled to %.1f L",
            reservoir_id, level,
        )
        return reservoir

    def get_by_state(self, state: ReservoirState) -> list[LiquidReservoir]:
        """Return all reservoirs in the given state."""
        return [r for r in self._reservoirs.values() if r.state == state]

    def get_available(self) -> list[LiquidReservoir]:
        """Return all FULL or PARTIAL reservoirs."""
        return [
            r for r in self._reservoirs.values()
            if r.state in (ReservoirState.FULL, ReservoirState.PARTIAL)
        ]

    def get_consumption_log(
        self, mission_id: Optional[str] = None,
    ) -> list[LiquidConsumptionRecord]:
        """Return consumption log, optionally filtered by mission."""
        if mission_id is not None:
            return [r for r in self._consumption_log if r.mission_id == mission_id]
        return list(self._consumption_log)

    def inventory_summary(self) -> dict:
        """Return a read-only summary of liquid inventory state."""
        total = len(self._reservoirs)
        total_capacity = sum(r.capacity_l for r in self._reservoirs.values())
        total_level = sum(r.current_level_l for r in self._reservoirs.values())
        return {
            "total_reservoirs": total,
            "by_state": {
                state.value: len(self.get_by_state(state))
                for state in ReservoirState
            },
            "total_capacity_l": round(total_capacity, 1),
            "total_current_l": round(total_level, 1),
            "fill_pct": round(total_level / total_capacity * 100, 1) if total_capacity > 0 else 0.0,
            "total_consumption_events": len(self._consumption_log),
        }


# =========================================================================
# Resource State Tracker
# =========================================================================

@dataclass
class DroneResourceState:
    """Resource state snapshot for a single drone."""
    drone_id: int
    battery_id: Optional[int] = None
    battery_charge_pct: Optional[float] = None
    battery_state: Optional[BatteryState] = None
    reservoir_id: Optional[int] = None
    liquid_level_l: Optional[float] = None
    liquid_capacity_l: Optional[float] = None
    reservoir_state: Optional[ReservoirState] = None


@dataclass
class ResourceSnapshot:
    """Immutable fleet-wide resource state snapshot."""
    battery_summary: dict
    liquid_summary: dict
    drone_resources: list[DroneResourceState]
    total_available_batteries: int
    total_available_reservoirs: int


class ResourceStateTracker:
    """
    Unified resource state tracking per drone.

    Integrates BatteryInventoryManager and LiquidInventoryManager to
    provide a single view of resource state across the fleet. Does
    NOT make allocation or scheduling decisions — purely aggregates
    and reports resource state.
    """

    def __init__(
        self,
        fleet: FleetRegistry,
        batteries: BatteryInventoryManager,
        liquids: LiquidInventoryManager,
    ) -> None:
        self._fleet = fleet
        self._batteries = batteries
        self._liquids = liquids

    def get_drone_resources(self, drone_id: int) -> DroneResourceState:
        """Get the current resource state for a specific drone."""
        self._fleet.get_drone(drone_id)

        battery_id: Optional[int] = None
        battery_charge: Optional[float] = None
        battery_state: Optional[BatteryState] = None
        reservoir_id: Optional[int] = None
        liquid_level: Optional[float] = None
        liquid_capacity: Optional[float] = None
        reservoir_state: Optional[ReservoirState] = None

        for b in self._batteries._batteries.values():
            if b.assigned_drone_id == drone_id:
                battery_id = b.battery_id
                battery_charge = b.charge_pct
                battery_state = b.state
                break

        for r in self._liquids._reservoirs.values():
            if r.assigned_drone_id == drone_id:
                reservoir_id = r.reservoir_id
                liquid_level = r.current_level_l
                liquid_capacity = r.capacity_l
                reservoir_state = r.state
                break

        return DroneResourceState(
            drone_id=drone_id,
            battery_id=battery_id,
            battery_charge_pct=battery_charge,
            battery_state=battery_state,
            reservoir_id=reservoir_id,
            liquid_level_l=liquid_level,
            liquid_capacity_l=liquid_capacity,
            reservoir_state=reservoir_state,
        )

    def get_fleet_resources(self) -> list[DroneResourceState]:
        """Get resource state for all drones in the fleet."""
        return [
            self.get_drone_resources(d.drone_id)
            for d in self._fleet.get_all()
        ]

    def build_snapshot(self) -> ResourceSnapshot:
        """
        Build an immutable snapshot of all resource state.

        Read-only aggregation — no state modification.
        """
        drone_resources = self.get_fleet_resources()

        snapshot = ResourceSnapshot(
            battery_summary=self._batteries.inventory_summary(),
            liquid_summary=self._liquids.inventory_summary(),
            drone_resources=drone_resources,
            total_available_batteries=len(self._batteries.get_available()),
            total_available_reservoirs=len(self._liquids.get_available()),
        )

        logger.info(
            "ResourceSnapshot: %d batteries available, %d reservoirs available",
            snapshot.total_available_batteries,
            snapshot.total_available_reservoirs,
        )
        return snapshot

    def get_mission_consumption(self, mission_id: str) -> dict:
        """
        Get resource consumption summary for a specific mission.

        Returns battery and liquid consumption records for the mission.
        """
        battery_records = self._batteries.get_consumption_log(mission_id=mission_id)
        liquid_records = self._liquids.get_consumption_log(mission_id=mission_id)

        total_battery_consumed = sum(r.consumed_pct for r in battery_records)
        total_liquid_consumed = sum(r.consumed_l for r in liquid_records)

        return {
            "mission_id": mission_id,
            "battery_consumption_events": len(battery_records),
            "total_battery_consumed_pct": round(total_battery_consumed, 1),
            "liquid_consumption_events": len(liquid_records),
            "total_liquid_consumed_l": round(total_liquid_consumed, 1),
        }
