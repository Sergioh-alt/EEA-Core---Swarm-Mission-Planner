"""
Phase 9.2 — Hardware Adapters Tests.

Tests for SimulationAdapter, PX4Adapter, ArduPilotAdapter.
Verifies:
- Each adapter implements BaseDroneInterface contract
- Command translation correctness
- Adapter compliance (no decision-making)
- Hive ↔ HAL contract tests
- Failure handling
"""

import ast

import pytest

from core.hal_interfaces import (
    BaseDroneInterface,
    CommandSchema,
    CommandType,
    ExecutionResult,
    ExecutionStatus,
    FlightState,
    HALErrorCode,
    TelemetrySchema,
)
from core.hal_adapters import (
    ArduPilotAdapter,
    PX4Adapter,
    SimulationAdapter,
)


# =========================================================================
# SimulationAdapter Tests
# =========================================================================

class TestSimulationAdapter:
    """Verify SimulationAdapter implements full contract."""

    def test_implements_interface(self):
        adapter = SimulationAdapter()
        assert isinstance(adapter, BaseDroneInterface)

    def test_adapter_name(self):
        adapter = SimulationAdapter()
        assert adapter.get_adapter_name() == "SimulationAdapter"

    def test_register_drone(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        assert adapter.is_connected(1)
        assert not adapter.is_connected(99)

    def test_duplicate_registration_rejected(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        with pytest.raises(ValueError):
            adapter.register_drone(1)

    def test_arm_disarm_cycle(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        r1 = adapter.arm(1)
        assert r1.status == ExecutionStatus.SUCCESS
        assert r1.telemetry.flight_state == FlightState.ARMED

        r2 = adapter.disarm(1)
        assert r2.status == ExecutionStatus.SUCCESS
        assert r2.telemetry.flight_state == FlightState.GROUNDED

    def test_full_flight_lifecycle(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)

        r_arm = adapter.arm(1)
        assert r_arm.status == ExecutionStatus.SUCCESS

        r_takeoff = adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
            params={"altitude_m": 20.0},
        ))
        assert r_takeoff.status == ExecutionStatus.SUCCESS
        assert r_takeoff.telemetry.flight_state == FlightState.IN_FLIGHT
        assert r_takeoff.telemetry.position.altitude_m == 20.0

        r_goto = adapter.send_command(CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "speed_m_s": 8.0},
        ))
        assert r_goto.status == ExecutionStatus.SUCCESS
        assert r_goto.telemetry.position.latitude == 40.0
        assert r_goto.telemetry.speed_m_s == 8.0

        r_land = adapter.send_command(CommandSchema(
            command_id="land-1", drone_id=1,
            command_type=CommandType.LAND,
        ))
        assert r_land.status == ExecutionStatus.SUCCESS
        assert r_land.telemetry.flight_state == FlightState.GROUNDED

    def test_spray_lifecycle(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))

        r_start = adapter.send_command(CommandSchema(
            command_id="spray-on", drone_id=1,
            command_type=CommandType.SPRAY_START,
        ))
        assert r_start.status == ExecutionStatus.SUCCESS

        r_stop = adapter.send_command(CommandSchema(
            command_id="spray-off", drone_id=1,
            command_type=CommandType.SPRAY_STOP,
        ))
        assert r_stop.status == ExecutionStatus.SUCCESS

    def test_emergency_stop(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))

        r = adapter.send_command(CommandSchema(
            command_id="estop-1", drone_id=1,
            command_type=CommandType.EMERGENCY_STOP,
        ))
        assert r.status == ExecutionStatus.SUCCESS
        assert r.telemetry.flight_state == FlightState.EMERGENCY

    def test_return_to_home(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))

        r = adapter.return_to_home(1)
        assert r.status == ExecutionStatus.SUCCESS
        assert r.telemetry.flight_state == FlightState.RETURNING

    def test_invalid_state_transitions(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)

        r_takeoff = adapter.send_command(CommandSchema(
            command_id="bad-takeoff", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        assert r_takeoff.status == ExecutionStatus.REJECTED

        r_goto = adapter.send_command(CommandSchema(
            command_id="bad-goto", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0},
        ))
        assert r_goto.status == ExecutionStatus.REJECTED

    def test_unregistered_drone_fails(self):
        adapter = SimulationAdapter()
        r = adapter.send_command(CommandSchema(
            command_id="cmd-1", drone_id=99,
            command_type=CommandType.ARM,
        ))
        assert r.status == ExecutionStatus.FAILED
        assert r.error.code == HALErrorCode.INVALID_STATE

    def test_disconnected_drone_fails(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.set_connected(1, False)
        r = adapter.arm(1)
        assert r.status == ExecutionStatus.FAILED
        assert r.error.code == HALErrorCode.COMMUNICATION_FAILURE

    def test_get_telemetry(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        t = adapter.get_telemetry(1)
        assert isinstance(t, TelemetrySchema)
        assert t.drone_id == 1
        assert t.flight_state == FlightState.GROUNDED
        assert t.battery_pct == 100.0

    def test_battery_simulation(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.set_battery(1, 50.0)
        t = adapter.get_telemetry(1)
        assert t.battery_pct == 50.0

    def test_command_log_records_all(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.disarm(1)
        assert len(adapter.command_log) == 2

    def test_set_speed(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        r = adapter.send_command(CommandSchema(
            command_id="speed-1", drone_id=1,
            command_type=CommandType.SET_SPEED,
            params={"speed_m_s": 12.0},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        assert r.telemetry.speed_m_s == 12.0


# =========================================================================
# PX4Adapter Tests
# =========================================================================

class TestPX4Adapter:
    """Verify PX4Adapter translates commands correctly."""

    def test_implements_interface(self):
        adapter = PX4Adapter()
        assert isinstance(adapter, BaseDroneInterface)

    def test_adapter_name(self):
        assert PX4Adapter().get_adapter_name() == "PX4Adapter"

    def test_register_and_connect(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        assert adapter.is_connected(1)
        assert not adapter.is_connected(99)

    def test_arm_translates_to_mavlink(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.arm(1)
        assert r.status == ExecutionStatus.SUCCESS
        assert len(adapter.translated_commands) == 1
        cmd = adapter.translated_commands[0]
        assert cmd["mavlink_command"] == "MAV_CMD_COMPONENT_ARM_DISARM"
        assert cmd["params"]["arm"] == 1

    def test_disarm_translates_to_mavlink(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.disarm(1)
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["params"]["arm"] == 0

    def test_takeoff_translates_altitude(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
            params={"altitude_m": 25.0},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mavlink_command"] == "MAV_CMD_NAV_TAKEOFF"
        assert cmd["params"]["altitude"] == 25.0

    def test_goto_translates_coordinates(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "altitude_m": 15.0},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mavlink_command"] == "MAV_CMD_NAV_WAYPOINT"
        assert cmd["params"]["latitude"] == 40.0

    def test_rth_translates(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.return_to_home(1)
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mavlink_command"] == "MAV_CMD_NAV_RETURN_TO_LAUNCH"

    def test_emergency_stop_force_disarm(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="estop-1", drone_id=1,
            command_type=CommandType.EMERGENCY_STOP,
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["params"]["force"] == 21196

    def test_unregistered_drone_fails(self):
        adapter = PX4Adapter()
        r = adapter.arm(99)
        assert r.status == ExecutionStatus.FAILED

    def test_get_telemetry_structural(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        t = adapter.get_telemetry(1)
        assert isinstance(t, TelemetrySchema)
        assert t.flight_state == FlightState.UNKNOWN

    def test_set_speed_translates(self):
        adapter = PX4Adapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="speed-1", drone_id=1,
            command_type=CommandType.SET_SPEED,
            params={"speed_m_s": 10.0},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mavlink_command"] == "MAV_CMD_DO_CHANGE_SPEED"
        assert cmd["params"]["speed"] == 10.0

    def test_all_command_types_mapped(self):
        for ct in CommandType:
            assert ct in PX4Adapter.PX4_COMMAND_MAP


# =========================================================================
# ArduPilotAdapter Tests
# =========================================================================

class TestArduPilotAdapter:
    """Verify ArduPilotAdapter translates commands correctly."""

    def test_implements_interface(self):
        adapter = ArduPilotAdapter()
        assert isinstance(adapter, BaseDroneInterface)

    def test_adapter_name(self):
        assert ArduPilotAdapter().get_adapter_name() == "ArduPilotAdapter"

    def test_register_and_connect(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        assert adapter.is_connected(1)
        assert not adapter.is_connected(99)

    def test_arm_translates(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        r = adapter.arm(1)
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mode"] == "ARM"

    def test_takeoff_guided_mode(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
            params={"altitude_m": 20.0},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mode"] == "GUIDED_TAKEOFF"
        assert cmd["params"]["altitude"] == 20.0
        assert cmd["params"]["mode"] == "GUIDED"

    def test_goto_with_frame(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mode"] == "GUIDED"
        assert cmd["params"]["frame"] == "GLOBAL_RELATIVE_ALT"

    def test_rth_rtl_mode(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        r = adapter.return_to_home(1)
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mode"] == "RTL"

    def test_spray_servo_control(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        r = adapter.send_command(CommandSchema(
            command_id="spray-on", drone_id=1,
            command_type=CommandType.SPRAY_START,
            params={"servo_channel": 9, "pwm_on": 1900},
        ))
        assert r.status == ExecutionStatus.SUCCESS
        cmd = adapter.translated_commands[0]
        assert cmd["mode"] == "SERVO_ON"
        assert cmd["params"]["pwm"] == 1900

    def test_unregistered_drone_fails(self):
        adapter = ArduPilotAdapter()
        r = adapter.arm(99)
        assert r.status == ExecutionStatus.FAILED

    def test_get_telemetry_structural(self):
        adapter = ArduPilotAdapter()
        adapter.register_drone(1)
        t = adapter.get_telemetry(1)
        assert isinstance(t, TelemetrySchema)

    def test_all_command_types_mapped(self):
        for ct in CommandType:
            assert ct in ArduPilotAdapter.ARDUPILOT_MODE_MAP


# =========================================================================
# Adapter Compliance Tests — No Decision-Making
# =========================================================================

class TestAdapterCompliance:
    """Verify adapters contain no decision-making logic."""

    HAL_MODULES = [
        "core/hal_interfaces.py",
        "core/hal_adapters.py",
    ]

    FORBIDDEN_PATTERNS = [
        "select_best", "choose_best", "pick_best", "find_best",
        "optimize", "rank", "score", "evaluate_fitness",
        "balance_load", "rebalance", "redistribute",
        "auto_assign", "auto_allocate", "smart_",
        "recommend", "suggest", "infer_priority",
        "schedule", "plan_mission", "plan_route",
    ]

    def test_no_forbidden_methods(self):
        for module_path in self.HAL_MODULES:
            with open(module_path, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                    for pattern in self.FORBIDDEN_PATTERNS:
                        assert pattern not in name, (
                            f"Forbidden pattern '{pattern}' in "
                            f"{module_path}:{node.lineno} — {node.name}"
                        )

    def test_no_ml_or_random_imports(self):
        forbidden_imports = [
            "import random", "from random", "import numpy",
            "sklearn", "tensorflow", "torch", "keras",
        ]
        for module_path in self.HAL_MODULES:
            with open(module_path, "r") as f:
                source = f.read()
            for imp in forbidden_imports:
                assert imp not in source, (
                    f"Forbidden import '{imp}' in {module_path}"
                )

    def test_no_hive_modification_imports(self):
        """HAL must not import Hive mutation methods."""
        with open("core/hal_adapters.py", "r") as f:
            source = f.read()
        assert "from core.hive" not in source
        assert "from core.mission_orchestrator" not in source
        assert "from core.fleet_manager" not in source
        assert "from core.resource_system" not in source
        assert "from core.hive_integration" not in source

    def test_no_phase07_imports(self):
        """HAL must not import planning/intelligence modules."""
        for module_path in self.HAL_MODULES:
            with open(module_path, "r") as f:
                source = f.read()
            forbidden = [
                "from core.swarm_planner", "from core.route_planner",
                "from core.resource_planner", "from core.risk_engine",
                "from core.decision_engine", "from core.swarm_optimizer",
                "from core.reallocation_engine", "from core.mission_adapter",
            ]
            for imp in forbidden:
                assert imp not in source, (
                    f"Planning import '{imp}' in {module_path}"
                )


# =========================================================================
# Hive ↔ HAL Contract Tests
# =========================================================================

class TestHiveHALContract:
    """Verify Hive output can be consumed by HAL."""

    def test_hive_mission_result_to_hal_commands(self):
        """Hive mission result can be translated to HAL command sequence."""
        from core.hive_integration import HiveController

        ctrl = HiveController()
        ctrl.submit_mission("m1", field_size_ha=50.0, crop_type="wheat", num_drones=4)
        result = ctrl.execute_next()
        assert result.success

        adapter = SimulationAdapter()
        for i in range(1, 5):
            adapter.register_drone(i)

        commands: list[ExecutionResult] = []
        for route in result.context.routes.routes:
            drone_id = route.drone_id
            arm_r = adapter.arm(drone_id)
            commands.append(arm_r)
            takeoff_r = adapter.send_command(CommandSchema(
                command_id=f"takeoff-{drone_id}",
                drone_id=drone_id,
                command_type=CommandType.TAKEOFF,
                params={"altitude_m": 10.0},
                mission_id="m1",
            ))
            commands.append(takeoff_r)
            for wp in route.waypoints:
                goto_r = adapter.send_command(CommandSchema(
                    command_id=f"goto-{drone_id}-{wp.sequence}",
                    drone_id=drone_id,
                    command_type=CommandType.GOTO,
                    params={"latitude": wp.x, "longitude": wp.y, "altitude_m": 10.0},
                    mission_id="m1",
                    sequence=wp.sequence,
                ))
                commands.append(goto_r)

        assert all(r.status == ExecutionStatus.SUCCESS for r in commands)

    def test_adapter_swappable(self):
        """Different adapters produce same execution status for same commands."""
        cmd = CommandSchema(
            command_id="test-arm", drone_id=1,
            command_type=CommandType.ARM,
        )

        sim = SimulationAdapter()
        sim.register_drone(1)
        px4 = PX4Adapter()
        px4.register_drone(1)
        ardu = ArduPilotAdapter()
        ardu.register_drone(1)

        r_sim = sim.send_command(cmd)
        r_px4 = px4.send_command(cmd)
        r_ardu = ardu.send_command(cmd)

        assert r_sim.status == ExecutionStatus.SUCCESS
        assert r_px4.status == ExecutionStatus.SUCCESS
        assert r_ardu.status == ExecutionStatus.SUCCESS

    def test_all_adapters_same_interface(self):
        """All adapters implement the same set of methods."""
        adapters = [SimulationAdapter(), PX4Adapter(), ArduPilotAdapter()]
        for adapter in adapters:
            assert hasattr(adapter, "send_command")
            assert hasattr(adapter, "get_telemetry")
            assert hasattr(adapter, "arm")
            assert hasattr(adapter, "disarm")
            assert hasattr(adapter, "return_to_home")
            assert hasattr(adapter, "is_connected")
            assert hasattr(adapter, "get_adapter_name")


# =========================================================================
# Multi-Drone Simulation Tests
# =========================================================================

class TestMultiDroneSimulation:
    """Verify multi-drone scenarios in simulation."""

    def test_four_drones_independent(self):
        adapter = SimulationAdapter()
        for i in range(1, 5):
            adapter.register_drone(i)

        adapter.arm(1)
        adapter.arm(2)
        t1 = adapter.get_telemetry(1)
        t3 = adapter.get_telemetry(3)
        assert t1.flight_state == FlightState.ARMED
        assert t3.flight_state == FlightState.GROUNDED

    def test_emergency_one_drone_no_effect_on_others(self):
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.register_drone(2)
        adapter.arm(1)
        adapter.arm(2)

        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        adapter.send_command(CommandSchema(
            command_id="takeoff-2", drone_id=2,
            command_type=CommandType.TAKEOFF,
        ))

        adapter.send_command(CommandSchema(
            command_id="estop-1", drone_id=1,
            command_type=CommandType.EMERGENCY_STOP,
        ))

        t1 = adapter.get_telemetry(1)
        t2 = adapter.get_telemetry(2)
        assert t1.flight_state == FlightState.EMERGENCY
        assert t2.flight_state == FlightState.IN_FLIGHT
