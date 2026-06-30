"""
Phase 10A — Simulation Core Tests.

Validates:
1. MAVLink Bridge (ACK/NACK/timeout/retry)
2. ROS2 Swarm Bus (state-only transport)
3. Failure Injection (battery, GPS, link, wind)
4. Simulation Core (multi-drone orchestration)
5. Architecture boundary enforcement
6. Single execution path (CommandSchema only)
7. Cross-layer isolation

NO runtime behavior changes to existing code.
"""

import ast
import os
import time

import pytest

from core.hal_interfaces import (
    CommandSchema,
    CommandType,
    ExecutionResult,
    ExecutionStatus,
    FlightState,
    TelemetrySchema,
)
from core.hal_adapters import SimulationAdapter
from simulation.mavlink_bridge import (
    MAVLinkACKResult,
    MAVLinkACKStatus,
    MAVLinkBridge,
    MAVLinkCommandEnvelope,
    MAVLINK_COMMAND_MAP,
    translate_to_envelope,
)
from simulation.ros2_swarm_bus import (
    BatteryMessage,
    DroneActivityState,
    DroneHealthStatus,
    DroneStateMessage,
    PositionMessage,
    SwarmBus,
    SwarmGlobalState,
    TaskAllocationMessage,
)
from simulation.failure_injection import (
    FailureConfig,
    FailureInjector,
    FailureSeverity,
    FailureType,
)
from simulation.sim_core import (
    FLIGHT_STATE_TO_ACTIVITY,
    SITLExecutor,
    SimulationCore,
)


# =========================================================================
# MAVLink Bridge Tests
# =========================================================================

class TestMAVLinkCommandTranslation:
    """Test CommandSchema → MAVLink envelope translation."""

    def test_all_command_types_have_mapping(self):
        for ct in CommandType:
            assert ct in MAVLINK_COMMAND_MAP

    def test_translate_arm(self):
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        env = translate_to_envelope(cmd)
        assert env.mavlink_command == "MAV_CMD_COMPONENT_ARM_DISARM"
        assert env.params["param1"] == 1.0

    def test_translate_disarm(self):
        cmd = CommandSchema(
            command_id="disarm-1", drone_id=1,
            command_type=CommandType.DISARM,
        )
        env = translate_to_envelope(cmd)
        assert env.mavlink_command == "MAV_CMD_COMPONENT_ARM_DISARM"
        assert env.params["param1"] == 0.0

    def test_translate_takeoff(self):
        cmd = CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
            params={"altitude_m": 20.0},
        )
        env = translate_to_envelope(cmd)
        assert env.mavlink_command == "MAV_CMD_NAV_TAKEOFF"
        assert env.params["param7"] == 20.0

    def test_translate_goto(self):
        cmd = CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "altitude_m": 15.0},
        )
        env = translate_to_envelope(cmd)
        assert env.mavlink_command == "MAV_CMD_NAV_WAYPOINT"
        assert env.params["param5"] == 40.0
        assert env.params["param6"] == -3.0
        assert env.params["param7"] == 15.0

    def test_translate_emergency_stop(self):
        cmd = CommandSchema(
            command_id="estop-1", drone_id=1,
            command_type=CommandType.EMERGENCY_STOP,
        )
        env = translate_to_envelope(cmd)
        assert env.params["param2"] == 21196.0

    def test_envelope_preserves_command_id(self):
        cmd = CommandSchema(
            command_id="unique-id-42", drone_id=5,
            command_type=CommandType.LAND,
        )
        env = translate_to_envelope(cmd)
        assert env.command_id == "unique-id-42"
        assert env.drone_id == 5

    def test_translation_deterministic(self):
        cmd = CommandSchema(
            command_id="test-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0},
        )
        e1 = translate_to_envelope(cmd)
        e2 = translate_to_envelope(cmd)
        assert e1.mavlink_command == e2.mavlink_command
        assert e1.params == e2.params


class TestMAVLinkBridge:
    """Test MAVLink Bridge ACK/NACK/timeout/retry."""

    def _make_bridge(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        executor = SITLExecutor(adapter)
        return MAVLinkBridge(executor), adapter

    def test_successful_command_ack(self):
        bridge, adapter = self._make_bridge()
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        result = bridge.execute_command(cmd)
        assert result.status == MAVLinkACKStatus.ACK
        assert result.attempts == 1

    def test_nack_on_invalid_state(self):
        bridge, adapter = self._make_bridge()
        cmd = CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        )
        result = bridge.execute_command(cmd)
        assert result.status == MAVLinkACKStatus.NACK

    def test_retry_count_on_nack(self):
        bridge, adapter = self._make_bridge()
        cmd = CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        )
        result = bridge.execute_command(cmd)
        assert result.attempts == 3  # max retries

    def test_command_log_populated(self):
        bridge, adapter = self._make_bridge()
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        bridge.execute_command(cmd)
        assert len(bridge.command_log) == 1
        assert bridge.command_log[0].status == MAVLinkACKStatus.ACK

    def test_to_execution_result_ack(self):
        bridge, _ = self._make_bridge()
        ack = MAVLinkACKResult(
            command_id="test", drone_id=1,
            status=MAVLinkACKStatus.ACK,
            mavlink_command="MAV_CMD_NAV_TAKEOFF",
            attempts=1,
        )
        result = bridge.to_execution_result(ack)
        assert result.status == ExecutionStatus.SUCCESS

    def test_to_execution_result_nack(self):
        bridge, _ = self._make_bridge()
        nack = MAVLinkACKResult(
            command_id="test", drone_id=1,
            status=MAVLinkACKStatus.NACK,
            mavlink_command="MAV_CMD_NAV_TAKEOFF",
            attempts=3,
            error_message="Rejected",
        )
        result = bridge.to_execution_result(nack)
        assert result.status == ExecutionStatus.REJECTED

    def test_to_execution_result_timeout(self):
        bridge, _ = self._make_bridge()
        timeout = MAVLinkACKResult(
            command_id="test", drone_id=1,
            status=MAVLinkACKStatus.TIMEOUT,
            mavlink_command="MAV_CMD_NAV_TAKEOFF",
            attempts=3,
        )
        result = bridge.to_execution_result(timeout)
        assert result.status == ExecutionStatus.TIMEOUT

    def test_max_retries_is_three(self):
        assert MAVLinkBridge.MAX_RETRIES == 3

    def test_timeout_is_3000ms(self):
        assert MAVLinkBridge.TIMEOUT_MS == 3000


# =========================================================================
# ROS2 Swarm Bus Tests
# =========================================================================

class TestSwarmBus:
    """Test ROS2 Swarm Bus — state-only transport."""

    def test_publish_drone_state(self):
        bus = SwarmBus()
        msg = DroneStateMessage(
            drone_id=1, timestamp_ms=1000,
            latitude=40.0, longitude=-3.0, altitude_m=15.0,
            battery_pct=85.0, state=DroneActivityState.ACTIVE,
        )
        bus.publish_drone_state(msg)
        latest = bus.get_latest(bus.drone_state_topic(1))
        assert latest == msg

    def test_publish_battery_topic(self):
        bus = SwarmBus()
        msg = DroneStateMessage(
            drone_id=1, timestamp_ms=1000, battery_pct=75.0,
        )
        bus.publish_drone_state(msg)
        battery = bus.get_latest(bus.drone_battery_topic(1))
        assert isinstance(battery, BatteryMessage)
        assert battery.percentage == 75.0

    def test_publish_position_topic(self):
        bus = SwarmBus()
        msg = DroneStateMessage(
            drone_id=1, timestamp_ms=1000,
            latitude=40.5, longitude=-3.5, altitude_m=20.0,
        )
        bus.publish_drone_state(msg)
        pos = bus.get_latest(bus.drone_position_topic(1))
        assert isinstance(pos, PositionMessage)
        assert pos.latitude == 40.5

    def test_publish_global_state(self):
        bus = SwarmBus()
        msg = SwarmGlobalState(
            total_drones=3, active_count=2, idle_count=1,
            timestamp_ms=1000,
        )
        bus.publish_global_state(msg)
        latest = bus.get_latest(bus.global_state_topic())
        assert latest == msg

    def test_publish_task_allocation(self):
        bus = SwarmBus()
        msg = TaskAllocationMessage(
            mission_id="m1",
            allocations=((1, "zone-A"), (2, "zone-B")),
            timestamp_ms=1000,
        )
        bus.publish_task_allocation(msg)
        latest = bus.get_latest(bus.task_allocation_topic())
        assert latest == msg

    def test_subscriber_receives_messages(self):
        bus = SwarmBus()
        received = []
        bus.subscribe("/drone_1/state", lambda t, m: received.append(m))
        msg = DroneStateMessage(drone_id=1, timestamp_ms=1000)
        bus.publish(bus.drone_state_topic(1), msg)
        assert len(received) == 1
        assert received[0] == msg

    def test_multiple_subscribers(self):
        bus = SwarmBus()
        r1, r2 = [], []
        bus.subscribe("/drone_1/state", lambda t, m: r1.append(m))
        bus.subscribe("/drone_1/state", lambda t, m: r2.append(m))
        msg = DroneStateMessage(drone_id=1, timestamp_ms=1000)
        bus.publish(bus.drone_state_topic(1), msg)
        assert len(r1) == 1
        assert len(r2) == 1

    def test_topic_naming_convention(self):
        assert SwarmBus.drone_state_topic(1) == "/drone_1/state"
        assert SwarmBus.drone_battery_topic(2) == "/drone_2/battery"
        assert SwarmBus.drone_position_topic(3) == "/drone_3/position"
        assert SwarmBus.global_state_topic() == "/swarm/global_state"
        assert SwarmBus.task_allocation_topic() == "/swarm/task_allocation"

    def test_message_count(self):
        bus = SwarmBus()
        assert bus.message_count == 0
        bus.publish("/test", "msg1")
        bus.publish("/test", "msg2")
        assert bus.message_count == 2

    def test_active_topics(self):
        bus = SwarmBus()
        bus.publish("/drone_1/state", "msg")
        bus.publish("/swarm/global_state", "msg")
        topics = bus.active_topics
        assert "/drone_1/state" in topics
        assert "/swarm/global_state" in topics

    def test_frozen_messages(self):
        """State messages are frozen (immutable)."""
        msg = DroneStateMessage(drone_id=1, timestamp_ms=1000)
        with pytest.raises(AttributeError):
            msg.drone_id = 2


# =========================================================================
# Failure Injection Tests
# =========================================================================

class TestFailureInjection:
    """Test failure injection system."""

    def test_battery_degradation(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.HIGH,
        ))
        inj.activate(FailureType.BATTERY_DEGRADATION)
        result = inj.apply_failures(
            drone_id=1, battery_pct=100.0,
            position_lat=40.0, position_lon=-3.0, position_alt=15.0,
            dt_seconds=1.0,
        )
        assert result["battery_pct"] < 100.0

    def test_gps_loss_critical(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.configure(FailureConfig(
            failure_type=FailureType.GPS_LOSS,
            severity=FailureSeverity.CRITICAL,
        ))
        inj.activate(FailureType.GPS_LOSS)
        result = inj.apply_failures(
            drone_id=1, battery_pct=100.0,
            position_lat=40.0, position_lon=-3.0, position_alt=15.0,
        )
        assert result["gps_available"] is False

    def test_link_loss_critical(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.configure(FailureConfig(
            failure_type=FailureType.LINK_LOSS,
            severity=FailureSeverity.CRITICAL,
        ))
        inj.activate(FailureType.LINK_LOSS)
        result = inj.apply_failures(
            drone_id=1, battery_pct=100.0,
            position_lat=40.0, position_lon=-3.0, position_alt=15.0,
        )
        assert result["link_available"] is False

    def test_wind_disturbance(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.configure(FailureConfig(
            failure_type=FailureType.WIND_DISTURBANCE,
            severity=FailureSeverity.HIGH,
        ))
        inj.activate(FailureType.WIND_DISTURBANCE)
        result = inj.apply_failures(
            drone_id=1, battery_pct=100.0,
            position_lat=40.0, position_lon=-3.0, position_alt=15.0,
        )
        assert result["wind_speed_m_s"] > 0

    def test_activate_deactivate(self):
        inj = FailureInjector()
        inj.configure(FailureConfig(
            failure_type=FailureType.GPS_LOSS,
        ))
        inj.activate(FailureType.GPS_LOSS)
        assert inj.is_active(FailureType.GPS_LOSS)
        inj.deactivate(FailureType.GPS_LOSS)
        assert not inj.is_active(FailureType.GPS_LOSS)

    def test_deactivate_all(self):
        inj = FailureInjector()
        for ft in FailureType:
            inj.configure(FailureConfig(failure_type=ft))
            inj.activate(ft)
        inj.deactivate_all()
        assert len(inj.active_failure_types) == 0

    def test_target_drone_ids(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.register_drone(2)
        inj.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.HIGH,
            target_drone_ids=[1],
        ))
        inj.activate(FailureType.BATTERY_DEGRADATION)
        r1 = inj.apply_failures(
            drone_id=1, battery_pct=100.0,
            position_lat=0, position_lon=0, position_alt=0,
        )
        r2 = inj.apply_failures(
            drone_id=2, battery_pct=100.0,
            position_lat=0, position_lon=0, position_alt=0,
        )
        assert r1["battery_pct"] < 100.0
        assert r2["battery_pct"] == 100.0

    def test_event_log(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.CRITICAL,
        ))
        inj.activate(FailureType.BATTERY_DEGRADATION)
        inj.apply_failures(
            drone_id=1, battery_pct=5.0,
            position_lat=0, position_lon=0, position_alt=0,
            dt_seconds=1.0,
        )
        assert len(inj.event_log) >= 1

    def test_no_failures_when_inactive(self):
        inj = FailureInjector(seed=42)
        inj.register_drone(1)
        inj.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.CRITICAL,
        ))
        result = inj.apply_failures(
            drone_id=1, battery_pct=100.0,
            position_lat=0, position_lon=0, position_alt=0,
        )
        assert result["battery_pct"] == 100.0


# =========================================================================
# Simulation Core Tests
# =========================================================================

class TestSimulationCore:
    """Test multi-drone simulation core."""

    def test_create_with_3_drones(self):
        sim = SimulationCore(num_drones=3)
        assert len(sim.drone_ids) == 3
        assert sim.drone_ids == [1, 2, 3]

    def test_create_with_2_drones(self):
        sim = SimulationCore(num_drones=2)
        assert len(sim.drone_ids) == 2

    def test_execute_command_through_bridge(self):
        sim = SimulationCore(num_drones=2)
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        result = sim.execute_command(cmd)
        assert result.status == ExecutionStatus.SUCCESS

    def test_command_rejected_for_unknown_drone(self):
        sim = SimulationCore(num_drones=2)
        cmd = CommandSchema(
            command_id="arm-99", drone_id=99,
            command_type=CommandType.ARM,
        )
        result = sim.execute_command(cmd)
        assert result.status == ExecutionStatus.FAILED

    def test_multi_drone_concurrent_commands(self):
        sim = SimulationCore(num_drones=3)
        results = []
        for drone_id in [1, 2, 3]:
            cmd = CommandSchema(
                command_id=f"arm-{drone_id}", drone_id=drone_id,
                command_type=CommandType.ARM,
            )
            results.append(sim.execute_command(cmd))
        assert all(r.status == ExecutionStatus.SUCCESS for r in results)

    def test_full_mission_sequence(self):
        sim = SimulationCore(num_drones=2)
        waypoints = [
            {"drone_id": 1, "latitude": 40.0, "longitude": -3.0},
            {"drone_id": 2, "latitude": 40.1, "longitude": -3.1},
        ]
        results = sim.execute_basic_mission("m1", waypoints)
        success_count = sum(
            1 for r in results if r.status == ExecutionStatus.SUCCESS
        )
        assert success_count >= 4  # at least arm + takeoff for 2 drones

    def test_state_published_to_bus_after_command(self):
        sim = SimulationCore(num_drones=2)
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        sim.execute_command(cmd)
        state = sim.bus.get_latest(SwarmBus.drone_state_topic(1))
        assert state is not None
        assert isinstance(state, DroneStateMessage)

    def test_tick_updates_state(self):
        sim = SimulationCore(num_drones=2)
        sim.tick()
        assert sim.tick_count == 1
        state = sim.bus.get_latest(SwarmBus.global_state_topic())
        assert state is not None
        assert isinstance(state, SwarmGlobalState)

    def test_failure_injection_through_tick(self):
        sim = SimulationCore(num_drones=2, failure_seed=42)
        sim.failure_injector.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.HIGH,
            target_drone_ids=[1],
        ))
        sim.failure_injector.activate(FailureType.BATTERY_DEGRADATION)
        sim.tick(dt_seconds=5.0)
        t = sim.get_telemetry(1)
        assert t.battery_pct < 100.0

    def test_link_loss_disconnects_drone(self):
        sim = SimulationCore(num_drones=2, failure_seed=42)
        sim.failure_injector.configure(FailureConfig(
            failure_type=FailureType.LINK_LOSS,
            severity=FailureSeverity.CRITICAL,
            target_drone_ids=[1],
        ))
        sim.failure_injector.activate(FailureType.LINK_LOSS)
        sim.tick()
        t = sim.get_telemetry(1)
        assert t.is_connected is False
        t2 = sim.get_telemetry(2)
        assert t2.is_connected is True

    def test_get_all_telemetry(self):
        sim = SimulationCore(num_drones=3)
        all_t = sim.get_all_telemetry()
        assert len(all_t) == 3
        for drone_id, t in all_t.items():
            assert isinstance(t, TelemetrySchema)

    def test_deterministic_with_seed(self):
        sim1 = SimulationCore(num_drones=2, failure_seed=42)
        sim1.failure_injector.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.HIGH,
        ))
        sim1.failure_injector.activate(FailureType.BATTERY_DEGRADATION)
        sim1.tick()
        t1 = sim1.get_telemetry(1)

        sim2 = SimulationCore(num_drones=2, failure_seed=42)
        sim2.failure_injector.configure(FailureConfig(
            failure_type=FailureType.BATTERY_DEGRADATION,
            severity=FailureSeverity.HIGH,
        ))
        sim2.failure_injector.activate(FailureType.BATTERY_DEGRADATION)
        sim2.tick()
        t2 = sim2.get_telemetry(1)

        assert t1.battery_pct == t2.battery_pct


# =========================================================================
# Architecture Boundary Enforcement Tests
# =========================================================================

class TestPhase10ABoundaryEnforcement:
    """Verify Phase 10A respects all architecture boundaries."""

    SIMULATION_MODULES = [
        "simulation/__init__.py",
        "simulation/mavlink_bridge.py",
        "simulation/ros2_swarm_bus.py",
        "simulation/failure_injection.py",
        "simulation/sim_core.py",
    ]

    def _get_imports(self, file_path: str) -> list[str]:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
        return imports

    def test_no_hive_imports_in_simulation(self):
        """Simulation modules must not import Hive."""
        hive_modules = {
            "core.hive", "core.hive_integration",
            "core.mission_orchestrator", "core.fleet_manager",
            "core.resource_system",
        }
        for module in self.SIMULATION_MODULES:
            if not os.path.exists(module):
                continue
            imports = self._get_imports(module)
            for imp in imports:
                assert imp not in hive_modules, (
                    f"Simulation module {module} imports Hive: {imp}"
                )

    def test_no_planning_imports_in_simulation(self):
        """Simulation modules must not import planning logic."""
        planning_modules = {
            "core.swarm_planner", "core.route_planner",
            "core.resource_planner", "core.risk_engine",
            "core.decision_engine", "core.swarm_optimizer",
        }
        for module in self.SIMULATION_MODULES:
            if not os.path.exists(module):
                continue
            imports = self._get_imports(module)
            for imp in imports:
                assert imp not in planning_modules, (
                    f"Simulation module {module} imports planning: {imp}"
                )

    def test_no_ui_imports_in_simulation(self):
        """Simulation modules must not import UI."""
        for module in self.SIMULATION_MODULES:
            if not os.path.exists(module):
                continue
            imports = self._get_imports(module)
            for imp in imports:
                assert not imp.startswith("ui."), (
                    f"Simulation module {module} imports UI: {imp}"
                )

    def test_no_decision_methods_in_simulation(self):
        """Simulation modules must not contain decision-making methods."""
        forbidden = [
            "decide", "choose_best", "select_best", "optimize",
            "plan_route", "allocate_resource", "schedule",
            "prioritize", "rank",
        ]
        for module in self.SIMULATION_MODULES:
            if not os.path.exists(module):
                continue
            with open(module, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                    for pat in forbidden:
                        assert pat not in name, (
                            f"Decision method '{node.name}' in {module}"
                        )

    def test_ros2_bus_has_no_logic(self):
        """ROS2 bus must be pure transport — no processing methods."""
        with open("simulation/ros2_swarm_bus.py", "r") as f:
            tree = ast.parse(f.read())
        forbidden = [
            "decide", "compute", "calculate", "analyze",
            "optimize", "plan", "evaluate", "infer",
        ]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pat in forbidden:
                    assert pat not in name, (
                        f"Logic method '{node.name}' in ROS2 bus"
                    )

    def test_mavlink_bridge_only_entry_is_command_schema(self):
        """MAVLink bridge accepts only CommandSchema — no direct MAVLink."""
        bridge_imports = self._get_imports("simulation/mavlink_bridge.py")
        core_imports = [i for i in bridge_imports if i.startswith("core.")]
        assert all(i == "core.hal_interfaces" for i in core_imports)

    def test_command_schema_is_single_execution_path(self):
        """Verify the execution path goes through CommandSchema only."""
        sim = SimulationCore(num_drones=2)
        cmd = CommandSchema(
            command_id="test-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        result = sim.execute_command(cmd)
        assert isinstance(result, ExecutionResult)
        assert len(sim.bridge.command_log) == 1

    def test_no_direct_mavlink_from_hive(self):
        """Verify Hive modules don't import MAVLink directly."""
        hive_files = [
            "core/hive.py", "core/hive_integration.py",
            "core/mission_orchestrator.py", "core/fleet_manager.py",
        ]
        for f in hive_files:
            if not os.path.exists(f):
                continue
            imports = self._get_imports(f)
            for imp in imports:
                assert "mavlink" not in imp.lower(), (
                    f"Hive module {f} imports MAVLink: {imp}"
                )
                assert not imp.startswith("simulation."), (
                    f"Hive module {f} imports simulation: {imp}"
                )

    def test_no_ui_imports_mavlink(self):
        """UI must not import MAVLink or simulation."""
        ui_dir = "ui"
        for filename in os.listdir(ui_dir):
            if not filename.endswith(".py"):
                continue
            filepath = os.path.join(ui_dir, filename)
            imports = self._get_imports(filepath)
            for imp in imports:
                assert "mavlink" not in imp.lower(), (
                    f"UI {filepath} imports MAVLink: {imp}"
                )
                assert not imp.startswith("simulation."), (
                    f"UI {filepath} imports simulation: {imp}"
                )

    def test_flight_state_to_activity_mapping_complete(self):
        """All FlightStates map to DroneActivityState."""
        for fs in FlightState:
            assert fs in FLIGHT_STATE_TO_ACTIVITY

    def test_existing_hal_tests_unaffected(self):
        """Phase 10A does not modify any existing HAL modules."""
        from core.hal_static_analyzer import run_full_enforcement
        result = run_full_enforcement()
        assert result.compliant


# =========================================================================
# Backward Compatibility
# =========================================================================

class TestPhase10ABackwardCompatibility:
    """Verify Phase 10A introduces no regressions."""

    def test_simulation_adapter_unchanged(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        result = adapter.send_command(cmd)
        assert result.status == ExecutionStatus.SUCCESS

    def test_hal_interfaces_unchanged(self):
        from core.hal_interfaces import (
            BaseDroneInterface, CommandType, FlightState,
            ExecutionStatus, HALErrorCode,
        )
        assert len(CommandType) == 10
        assert len(FlightState) == 9
        assert len(ExecutionStatus) == 5
        assert len(HALErrorCode) == 9

    def test_pipeline_unchanged(self):
        from core.hive_integration import HiveController
        ctrl = HiveController()
        ctrl.submit_mission(
            "m1", field_size_ha=30.0, crop_type="corn", num_drones=3,
        )
        result = ctrl.execute_next()
        assert result.success
