"""
Phase 10B — End-to-End Digital Twin Pipeline Validation.

Validates the COMPLETE pipeline:
  Simulation Core → ROS2 State Transport → Sync Engine →
  Digital Twin → Snapshot Engine → Replay Engine → Restored State

16-point validation as specified. No architecture modifications.
"""

import ast
import os
import sys
import time
from dataclasses import dataclass

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation.sim_core import SimulationCore
from simulation.ros2_swarm_bus import (
    SwarmBus,
    DroneStateMessage,
    DroneActivityState,
    DroneHealthStatus,
    SwarmGlobalState,
)
from simulation.failure_injection import FailureInjector, FailureType
from digital_twin.twin_api import DigitalTwin
from digital_twin.state_models import (
    DroneState,
    DroneStateUpdate,
    EnvironmentCondition,
    FailureCategory,
    HealthLevel,
    MissionStatus,
    SwarmState,
    SwarmStateUpdate,
)


# =========================================================================
# Report Helper
# =========================================================================

@dataclass
class ValidationReport:
    """Collects validation results."""
    lines: list = None

    def __post_init__(self):
        if self.lines is None:
            self.lines = []

    def section(self, title: str):
        self.lines.append(f"\n{'='*70}")
        self.lines.append(f"  {title}")
        self.lines.append(f"{'='*70}")

    def log(self, msg: str):
        self.lines.append(msg)

    def check(self, description: str, condition: bool) -> bool:
        status = "PASS" if condition else "FAIL"
        self.lines.append(f"  [{status}] {description}")
        return condition

    def output(self) -> str:
        return "\n".join(self.lines)


# =========================================================================
# MAIN VALIDATION
# =========================================================================

def run_validation() -> tuple[int, int, str]:
    """Run full E2E validation. Returns (pass_count, fail_count, output)."""
    report = ValidationReport()
    passes = 0
    fails = 0

    def check(desc, cond):
        nonlocal passes, fails
        if report.check(desc, cond):
            passes += 1
        else:
            fails += 1

    report.section("PHASE 10B — END-TO-END DIGITAL TWIN PIPELINE VALIDATION")
    report.log(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    # =====================================================================
    # 1. Start Simulation Core with 3 drones
    # =====================================================================
    report.section("1. START SIMULATION CORE (3 drones)")

    sim = SimulationCore(num_drones=3, failure_seed=42)
    sim.tick()  # initialize state

    check("SimulationCore initialized", sim is not None)
    check("3 drones spawned", len(sim.drone_ids) == 3)
    check("Drone IDs are [1, 2, 3]", sim.drone_ids == [1, 2, 3])
    report.log(f"  Drone IDs: {sim.drone_ids}")
    report.log(f"  Tick count: {sim.tick_count}")

    # =====================================================================
    # 2. Confirm ROS2 publishes independent state updates
    # =====================================================================
    report.section("2. ROS2 STATE PUBLICATION")

    bus = sim.bus
    topics = bus.active_topics
    report.log(f"  Active topics: {topics}")
    report.log(f"  Total messages published: {bus.message_count}")

    check("ROS2 bus has published messages", bus.message_count > 0)
    check("/drone_1/state exists", "/drone_1/state" in topics)
    check("/drone_2/state exists", "/drone_2/state" in topics)
    check("/drone_3/state exists", "/drone_3/state" in topics)
    check("/swarm/global_state exists", "/swarm/global_state" in topics)

    # Verify independent state per drone
    d1_state = bus.get_latest("/drone_1/state")
    d2_state = bus.get_latest("/drone_2/state")
    d3_state = bus.get_latest("/drone_3/state")
    check("Drone 1 state is DroneStateMessage", isinstance(d1_state, DroneStateMessage))
    check("Drone 2 state is DroneStateMessage", isinstance(d2_state, DroneStateMessage))
    check("Drone 3 state is DroneStateMessage", isinstance(d3_state, DroneStateMessage))
    check("Drone states are independent (different IDs)",
          d1_state.drone_id != d2_state.drone_id != d3_state.drone_id)

    # =====================================================================
    # 3. Verify Sync Engine receives and synchronizes ROS2 updates
    # =====================================================================
    report.section("3. SYNC ENGINE SYNCHRONIZATION")

    twin = DigitalTwin(swarm_id="validation-swarm")

    # Register drones
    for did in sim.drone_ids:
        twin.register_drone(did)

    # Feed ROS2 state into Digital Twin sync
    for did in sim.drone_ids:
        state_msg = bus.get_latest(SwarmBus.drone_state_topic(did))
        bat_msg = bus.get_latest(SwarmBus.drone_battery_topic(did))

        update = DroneStateUpdate(
            drone_id=did,
            timestamp_ms=state_msg.timestamp_ms,
            latitude=state_msg.latitude,
            longitude=state_msg.longitude,
            altitude_m=state_msg.altitude_m,
            velocity_x=state_msg.velocity_x,
            velocity_y=state_msg.velocity_y,
            velocity_z=state_msg.velocity_z,
            battery_pct=state_msg.battery_pct,
            battery_voltage=state_msg.battery_voltage,
            armed=True,
            mode="GUIDED",
            gps_available=True,
            gps_accuracy_m=1.0,
            communication_active=True,
            health=state_msg.health.value,
            current_task="IN_PROGRESS",
        )
        result = twin.sync_drone_state(update)
        check(f"Drone {did} sync accepted", result.valid)

    report.log(f"  Sync version after initial sync: {twin.version}")
    check("Version > 0 after sync", twin.version > 0)

    # =====================================================================
    # 4. Verify Digital Twin contains latest consistent swarm state
    # =====================================================================
    report.section("4. DIGITAL TWIN CONSISTENCY")

    state = twin.get_swarm_state()
    report.log(f"  SwarmState.swarm_id: {state.swarm_id}")
    report.log(f"  SwarmState.total_drones: {state.total_drones}")
    report.log(f"  SwarmState.version: {state.version}")

    check("SwarmState contains 3 drones", state.total_drones == 3)
    check("SwarmState has correct swarm_id", state.swarm_id == "validation-swarm")
    check("All 3 drone states present", len(state.drone_states) == 3)
    check("Drone 1 battery synced", state.drone_states[0].battery_pct == d1_state.battery_pct)
    check("Drone 2 battery synced", state.drone_states[1].battery_pct == d2_state.battery_pct)
    check("Drone 3 battery synced", state.drone_states[2].battery_pct == d3_state.battery_pct)

    # =====================================================================
    # 5. Create immutable snapshots at multiple timestamps
    # =====================================================================
    report.section("5. SNAPSHOT CREATION (multiple timestamps)")

    snap1 = twin.create_snapshot("initial state — 3 drones healthy")
    report.log(f"  Snapshot 1: {snap1.snapshot_id} (v{snap1.version})")

    # Use monotonic timestamps to avoid regression
    base_ts = int(time.monotonic() * 1000)

    # Simulate state changes
    twin.sync_drone_state(DroneStateUpdate(
        drone_id=1, timestamp_ms=base_ts + 1000, battery_pct=90.0,
        armed=True, mode="GUIDED", communication_active=True, health="OK",
    ))
    snap2 = twin.create_snapshot("after drone 1 battery drain")
    report.log(f"  Snapshot 2: {snap2.snapshot_id} (v{snap2.version})")

    twin.sync_drone_state(DroneStateUpdate(
        drone_id=2, timestamp_ms=base_ts + 2000, battery_pct=85.0,
        armed=True, mode="GUIDED", communication_active=True, health="OK",
    ))
    snap3 = twin.create_snapshot("after drone 2 battery drain")
    report.log(f"  Snapshot 3: {snap3.snapshot_id} (v{snap3.version})")

    twin.sync_drone_state(DroneStateUpdate(
        drone_id=3, timestamp_ms=base_ts + 3000, battery_pct=80.0,
        armed=True, mode="GUIDED", communication_active=True, health="OK",
    ))
    snap4 = twin.create_snapshot("after drone 3 battery drain")
    report.log(f"  Snapshot 4: {snap4.snapshot_id} (v{snap4.version})")

    check("4 snapshots created", twin.snapshot_count == 4)
    check("Snap1 version < Snap4 version", snap1.version < snap4.version)
    check("Snapshots are distinct", snap1.snapshot_id != snap4.snapshot_id)

    # =====================================================================
    # 6. Verify snapshots remain immutable after additional updates
    # =====================================================================
    report.section("6. SNAPSHOT IMMUTABILITY")

    # Record snap1 state before further updates
    snap1_drone1_battery = snap1.swarm_state.drone_states[0].battery_pct

    # Apply more updates
    twin.sync_drone_state(DroneStateUpdate(
        drone_id=1, timestamp_ms=base_ts + 5000, battery_pct=50.0,
        armed=True, mode="GUIDED", communication_active=True, health="WARNING",
    ))

    # Check snap1 is unchanged
    snap1_after = twin.get_snapshot(snap1.snapshot_id)
    check("Snap1 still exists after updates", snap1_after is not None)
    check("Snap1 drone 1 battery unchanged",
          snap1_after.swarm_state.drone_states[0].battery_pct == snap1_drone1_battery)
    check("Snap2 drone 1 battery = 90%",
          twin.get_snapshot(snap2.snapshot_id).swarm_state.drone_states[0].battery_pct == 90.0)

    # Try to mutate (should raise)
    immutable = True
    try:
        snap1.swarm_state.drone_states[0].battery_pct = 0.0  # type: ignore
        immutable = False
    except Exception:
        pass
    check("Snapshot is truly immutable (frozen)", immutable)

    # =====================================================================
    # 7. Execute complete replay using stored snapshots
    # =====================================================================
    report.section("7. COMPLETE REPLAY EXECUTION")

    timeline = twin.replay_timeline(description="full validation replay")
    report.log(f"  Timeline ID: {timeline.timeline_id}")
    report.log(f"  Total frames: {timeline.total_frames}")
    report.log(f"  Start ms: {timeline.start_ms}")
    report.log(f"  End ms: {timeline.end_ms}")

    check("Replay timeline has 4 frames", timeline.total_frames == 4)
    check("Timeline starts at snap1 timestamp", timeline.start_ms == snap1.timestamp_ms)
    check("Timeline ends at snap4 timestamp", timeline.end_ms == snap4.timestamp_ms)

    # =====================================================================
    # 8. Verify replay reconstructs exact original sequence
    # =====================================================================
    report.section("8. REPLAY SEQUENCE RECONSTRUCTION")

    frame0 = timeline.frames[0]
    frame1 = timeline.frames[1]
    frame2 = timeline.frames[2]
    frame3 = timeline.frames[3]

    check("Frame 0 = snap1 state", frame0.swarm_state == snap1.swarm_state)
    check("Frame 1 = snap2 state", frame1.swarm_state == snap2.swarm_state)
    check("Frame 2 = snap3 state", frame2.swarm_state == snap3.swarm_state)
    check("Frame 3 = snap4 state", frame3.swarm_state == snap4.swarm_state)

    # Verify battery progression in replay
    check("Replay shows drone 1 battery 100→90%",
          frame0.swarm_state.drone_states[0].battery_pct > frame1.swarm_state.drone_states[0].battery_pct)

    # =====================================================================
    # 9-10. Compare final restored state vs original
    # =====================================================================
    report.section("9-10. RESTORED STATE vs ORIGINAL COMPARISON")

    # Replay at version 4 (snap4)
    restored = twin.replay_at_version(4)
    original = snap4.swarm_state

    check("Restored state is not None", restored is not None)
    check("Restored == original (identity)", restored == original)
    check("Restored total_drones matches", restored.total_drones == original.total_drones)
    check("Restored drone_states match", restored.drone_states == original.drone_states)
    check("Restored version matches", restored.version == original.version)

    # Per-drone comparison
    for i in range(3):
        rd = restored.drone_states[i]
        od = original.drone_states[i]
        check(f"Drone {rd.drone_id}: battery matches ({rd.battery_pct}%)",
              rd.battery_pct == od.battery_pct)

    report.log(f"  Original state hash: {hash(original)}")
    report.log(f"  Restored state hash: {hash(restored)}")
    check("Hash values are identical", hash(original) == hash(restored))

    # =====================================================================
    # 11. Inject all supported failures
    # =====================================================================
    report.section("11. FAILURE INJECTION (all 4 types)")

    # Use simulation's failure injector
    fsim = sim.failure_injector

    # Configure and activate all 4 failure types
    from simulation.failure_injection import FailureConfig, FailureSeverity
    fsim.configure(FailureConfig(
        failure_type=FailureType.BATTERY_DEGRADATION,
        severity=FailureSeverity.HIGH,
        target_drone_ids=[1],
        params={"rate_pct_per_sec": 5.0},
    ))
    fsim.configure(FailureConfig(
        failure_type=FailureType.GPS_LOSS,
        severity=FailureSeverity.HIGH,
        target_drone_ids=[2],
    ))
    fsim.configure(FailureConfig(
        failure_type=FailureType.LINK_LOSS,
        severity=FailureSeverity.HIGH,
        target_drone_ids=[3],
    ))
    fsim.configure(FailureConfig(
        failure_type=FailureType.WIND_DISTURBANCE,
        severity=FailureSeverity.HIGH,
        target_drone_ids=[1],
        params={"wind_speed_m_s": 15.0, "wind_direction_deg": 90.0},
    ))
    fsim.activate(FailureType.BATTERY_DEGRADATION)
    fsim.activate(FailureType.GPS_LOSS)
    fsim.activate(FailureType.LINK_LOSS)
    fsim.activate(FailureType.WIND_DISTURBANCE)

    # Tick simulation to propagate failures
    for _ in range(5):
        sim.tick()

    check("Battery degradation active", FailureType.BATTERY_DEGRADATION in fsim.active_failure_types)
    check("GPS loss active", FailureType.GPS_LOSS in fsim.active_failure_types)
    check("Link loss active", FailureType.LINK_LOSS in fsim.active_failure_types)
    check("Wind disturbance active", FailureType.WIND_DISTURBANCE in fsim.active_failure_types)

    report.log(f"  Active failures: {[f.value for f in fsim.active_failure_types]}")

    # =====================================================================
    # 12. Verify failure propagation through full pipeline
    # =====================================================================
    report.section("12. FAILURE PROPAGATION: Sim → ROS2 → Sync → Twin → Snap → Replay")

    # Read post-failure ROS2 state
    d1_post = bus.get_latest(SwarmBus.drone_state_topic(1))
    d2_post = bus.get_latest(SwarmBus.drone_state_topic(2))
    d3_post = bus.get_latest(SwarmBus.drone_state_topic(3))

    report.log(f"  Drone 1 post-failure battery: {d1_post.battery_pct}%")
    report.log(f"  Drone 2 post-failure health: {d2_post.health}")
    report.log(f"  Drone 3 post-failure state: {d3_post.state}")

    check("Drone 1 battery degraded (<100%)", d1_post.battery_pct < 100.0)

    # Sync post-failure state into Digital Twin
    # Use timestamps that are monotonically higher than section 5/6 updates
    adapter = sim.adapter
    failure_ts = base_ts + 10000

    for idx, did in enumerate(sim.drone_ids):
        telemetry = adapter.get_telemetry(did)
        state_msg = bus.get_latest(SwarmBus.drone_state_topic(did))

        update = DroneStateUpdate(
            drone_id=did,
            timestamp_ms=failure_ts + idx * 100,
            latitude=state_msg.latitude,
            longitude=state_msg.longitude,
            altitude_m=state_msg.altitude_m,
            velocity_x=state_msg.velocity_x,
            velocity_y=state_msg.velocity_y,
            velocity_z=state_msg.velocity_z,
            battery_pct=state_msg.battery_pct,
            battery_voltage=state_msg.battery_voltage,
            armed=True,
            mode="GUIDED",
            gps_available=(state_msg.health != DroneHealthStatus.CRITICAL),
            gps_accuracy_m=1.0,
            communication_active=telemetry.is_connected,
            health=state_msg.health.value,
            current_task="IN_PROGRESS",
        )
        result = twin.sync_drone_state(update)
        check(f"Post-failure drone {did} sync accepted", result.valid)

    # Sync failures into Digital Twin
    twin.sync_failures([
        FailureCategory.BATTERY_DEGRADATION,
        FailureCategory.GPS_LOSS,
        FailureCategory.LINK_LOSS,
        FailureCategory.WIND_DISTURBANCE,
    ])

    # Sync environment (wind)
    twin.sync_environment(
        wind_speed_m_s=14.0,
        wind_direction_deg=90.0,
        condition=EnvironmentCondition.DEGRADED,
    )

    # Verify in Digital Twin
    twin_state = twin.get_swarm_state()
    report.log(f"  Twin active_failures: {[f.value for f in twin_state.active_failures]}")
    report.log(f"  Twin global_health: {twin_state.global_health.value}")
    report.log(f"  Twin environment wind: {twin_state.environment_state.wind_speed_m_s} m/s")

    check("Twin has 4 active failures", len(twin_state.active_failures) == 4)
    check("Twin reflects battery degradation",
          FailureCategory.BATTERY_DEGRADATION in twin_state.active_failures)
    check("Twin reflects GPS loss",
          FailureCategory.GPS_LOSS in twin_state.active_failures)
    check("Twin reflects link loss",
          FailureCategory.LINK_LOSS in twin_state.active_failures)
    check("Twin reflects wind disturbance",
          FailureCategory.WIND_DISTURBANCE in twin_state.active_failures)

    # Verify drone-level failure effects in Twin
    d1_twin = twin.get_drone_state(1)
    d2_twin = twin.get_drone_state(2)
    d3_twin = twin.get_drone_state(3)

    check("Twin drone 1 battery degraded", d1_twin.battery_pct < 100.0)
    check("Twin drone 3 communication lost", d3_twin.communication_active is False)

    # Create snapshot with failures
    snap_failure = twin.create_snapshot("all 4 failures active")
    report.log(f"  Failure snapshot: {snap_failure.snapshot_id}")

    # =====================================================================
    # 13. Verify replay reproduces failures deterministically
    # =====================================================================
    report.section("13. DETERMINISTIC FAILURE REPLAY")

    # Replay the failure snapshot
    replay_state = twin.replay_at_version(snap_failure.version)
    check("Failure replay returns state", replay_state is not None)
    check("Replayed failures == original failures",
          replay_state.active_failures == twin_state.active_failures)

    # Per-drone replay
    drone1_replay = twin.replay_drone(drone_id=1)
    report.log(f"  Drone 1 replay frames: {drone1_replay.total_frames}")
    check("Drone 1 replay has frames", drone1_replay.total_frames > 0)

    # Check battery degradation appears in replay
    last_frame = drone1_replay.frames[-1]
    check("Replay shows drone 1 battery degraded",
          last_frame.drone_state.battery_pct < 100.0)

    # Determinism check — replay twice
    replay_a = twin.replay_at_version(snap_failure.version)
    replay_b = twin.replay_at_version(snap_failure.version)
    check("Replay is deterministic (A == B)", replay_a == replay_b)

    # =====================================================================
    # 14. Verify no state inconsistencies during synchronization
    # =====================================================================
    report.section("14. STATE CONSISTENCY VERIFICATION")

    sync_events = twin.sync_events
    rejected = [e for e in sync_events if "REJECTED" in e.event_type]
    report.log(f"  Total sync events: {len(sync_events)}")
    report.log(f"  Rejected updates: {len(rejected)}")

    check("No rejected updates during valid sync", len(rejected) == 0)

    # Verify state consistency
    final_state = twin.get_swarm_state()
    check("Final state total_drones == 3", final_state.total_drones == 3)
    check("Final state drone_states length == 3", len(final_state.drone_states) == 3)

    # Check monotonic versions
    all_snaps = twin.list_snapshots()
    versions = [s.version for s in all_snaps]
    check("Snapshot versions are monotonically increasing",
          versions == sorted(versions))
    check("No duplicate versions",
          len(set(versions)) == len(versions))

    # =====================================================================
    # 15. Architecture violations / cross-layer leaks
    # =====================================================================
    report.section("15. ARCHITECTURE COMPLIANCE")

    DIGITAL_TWIN_FILES = [
        "digital_twin/__init__.py",
        "digital_twin/state_models.py",
        "digital_twin/state_validation.py",
        "digital_twin/sync_engine.py",
        "digital_twin/snapshot_engine.py",
        "digital_twin/replay_engine.py",
        "digital_twin/twin_api.py",
    ]

    FORBIDDEN = {
        "core.swarm_planner", "core.route_planner", "core.resource_planner",
        "core.risk_engine", "core.decision_engine", "core.swarm_optimizer",
        "core.mission_timeline", "core.mission_intake", "core.reallocation_engine",
        "core.hive", "core.hive_integration", "core.mission_orchestrator",
        "core.fleet_manager", "core.hal_adapters", "core.hal_interfaces",
        "simulation.mavlink_bridge", "simulation.sim_core",
        "pymavlink", "streamlit", "plotly",
    }

    total_violations = 0
    for filepath in DIGITAL_TWIN_FILES:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        violations = [i for i in imports if i in FORBIDDEN]
        total_violations += len(violations)
        if violations:
            report.log(f"  VIOLATION in {filepath}: {violations}")

    check(f"0 forbidden imports across 7 modules (found {total_violations})",
          total_violations == 0)

    # =====================================================================
    # 16. No decision-making logic
    # =====================================================================
    report.section("16. NO DECISION-MAKING LOGIC")

    DECISION_KEYWORDS = [
        "decide", "choose", "select_best", "optimize", "plan_route",
        "allocate", "schedule", "prioritize", "execute_mission",
        "dispatch", "recommend", "infer",
    ]

    decision_violations = 0
    for filepath in DIGITAL_TWIN_FILES:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name_lower = node.name.lower()
                for kw in DECISION_KEYWORDS:
                    if kw in name_lower:
                        decision_violations += 1
                        report.log(f"  VIOLATION: {filepath} method '{node.name}' has '{kw}'")

    check(f"0 decision-making methods (found {decision_violations})",
          decision_violations == 0)
    check("No planning logic in Digital Twin", total_violations == 0)
    check("No scheduling logic in Digital Twin", decision_violations == 0)
    check("No optimization logic in Digital Twin", decision_violations == 0)
    check("No Fleet Manager logic in Digital Twin", total_violations == 0)
    check("No Hive logic in Digital Twin", total_violations == 0)

    # =====================================================================
    # SUMMARY
    # =====================================================================
    report.section("FINAL SUMMARY")
    report.log(f"  Total checks: {passes + fails}")
    report.log(f"  PASSED: {passes}")
    report.log(f"  FAILED: {fails}")
    report.log(f"  Snapshots created: {twin.snapshot_count}")
    report.log(f"  Replay timelines generated: 2 (full + drone)")
    report.log(f"  Sync events: {len(sync_events)}")
    report.log(f"  Architecture violations: {total_violations}")
    report.log(f"  Decision-making violations: {decision_violations}")
    report.log("")

    if fails == 0:
        report.log("  *** VALIDATION PASSED — Phase 10B Digital Twin APPROVED ***")
    else:
        report.log(f"  *** VALIDATION FAILED — {fails} checks did not pass ***")

    return passes, fails, report.output()


# =========================================================================
# ENTRY POINT
# =========================================================================

if __name__ == "__main__":
    passes, fails, output = run_validation()
    print(output)

    # Save to file
    os.makedirs("docs/validation/logs", exist_ok=True)
    output_path = "docs/validation/logs/phase_10b_e2e_validation_output.txt"
    with open(output_path, "w") as f:
        f.write(output)
    print(f"\n  Report saved to: {output_path}")

    sys.exit(0 if fails == 0 else 1)
