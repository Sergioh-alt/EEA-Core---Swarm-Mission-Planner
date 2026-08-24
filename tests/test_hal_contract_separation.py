"""
Phase 9.7 — System Contract Separation & Architecture Isolation Tests.

Validates strict isolation between system layers:
- Simulation Layer Contract (SLC)
- IoV Communication Contract (IoV-C)
- Digital Twin Contract (DTC)

Performs:
- Architecture isolation tests
- Cross-layer leak detection (AST/static analysis)
- Contract consistency tests
- Schema identity verification

NO new runtime features. Validation only.
"""

import ast
import os

import pytest

from core.hal_interfaces import (
    BaseDroneInterface,
    CommandSchema,
    CommandType,
    ExecutionResult,
    ExecutionStatus,
    FlightState,
    GPSPosition,
    HALError,
    HALErrorCode,
    TelemetrySchema,
)
from core.hal_adapters import (
    ArduPilotAdapter,
    PX4Adapter,
    SimulationAdapter,
)
from core.hal_telemetry import (
    DroneTelemetryFrame,
    FleetTelemetrySnapshot,
    GPSFixQuality,
    TaskState,
    TelemetryStreamProcessor,
    FLIGHT_STATE_TO_TASK,
)
from core.hal_safety import (
    EmergencySignalHandler,
    EmergencyType,
    FailSafeState,
    FailSafeStateMapper,
    SafetyCommandRelay,
)

UI_SRC_DIR = os.path.join("orion-ui", "src")
UI_SOURCE_SUFFIXES = (".ts", ".tsx")


def ui_import_lines() -> list[tuple[str, str]]:
    """
    (path, line) for every import/export statement in the Mission Control UI.

    Only module-resolution statements are scanned: prose in comments and docs
    legitimately names the layers the UI is forbidden to reach.
    """
    lines: list[tuple[str, str]] = []
    scanned = 0
    for dirpath, _dirnames, filenames in os.walk(UI_SRC_DIR):
        for filename in filenames:
            if not filename.endswith(UI_SOURCE_SUFFIXES):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            scanned += 1
            for raw in source.splitlines():
                line = raw.strip()
                if line.startswith(("import ", "export ")) or "require(" in line:
                    lines.append((path, line))
    assert scanned > 0, f"No UI sources found under {UI_SRC_DIR}"
    return lines


# =========================================================================
# Architecture Isolation Tests
# =========================================================================

class TestArchitectureIsolation:
    """Verify no cross-layer leakage between system layers."""

    # --- Simulation → Hive isolation ---

    def test_no_simulation_to_hive_imports(self):
        """SimulationAdapter (in hal_adapters) must not import Hive modules."""
        with open("core/hal_adapters.py", "r") as f:
            source = f.read()
        hive_imports = [
            "from core.hive ", "from core.hive_integration ",
            "from core.mission_orchestrator ", "from core.fleet_manager ",
            "from core.resource_system ",
        ]
        for imp in hive_imports:
            assert imp not in source, (
                f"Simulation/Adapter imports Hive: '{imp}'"
            )

    def test_no_simulation_to_hal_write_access(self):
        """Simulation produces telemetry but cannot write to HAL state."""
        adapter = SimulationAdapter()
        adapter.register_drone(1)
        t = adapter.get_telemetry(1)
        assert isinstance(t, TelemetrySchema)
        assert not hasattr(t, "write_to_hal")
        assert not hasattr(t, "modify_state")
        assert not hasattr(t, "update_hive")

    # UI -> HAL / Hive isolation is enforced against the current Mission
    # Control UI by TestCrossLayerLeakDetection.test_ui_no_hal_imports and
    # .test_ui_no_hive_imports.

    def test_no_ros2_to_hive_decision_logic(self):
        """No ROS2 module exists that leaks decision logic into Hive."""
        ros2_patterns = ["import rclpy", "from rclpy", "ros2", "rospy"]
        for module in [
            "core/hal_adapters.py", "core/hal_telemetry.py",
            "core/hal_safety.py", "core/hal_interfaces.py",
        ]:
            with open(module, "r") as f:
                source = f.read().lower()
            for pat in ros2_patterns:
                assert pat not in source, (
                    f"ROS2 import found in {module}: '{pat}'"
                )

    def test_hal_modules_isolated_from_planning(self):
        """HAL modules must not import any Phase 0-7 planning modules."""
        planning_imports = [
            "from core.swarm_planner", "from core.route_planner",
            "from core.resource_planner", "from core.risk_engine",
            "from core.decision_engine", "from core.swarm_optimizer",
            "from core.reallocation_engine", "from core.mission_adapter",
            "from core.swarm_state", "from core.mission_intake",
            "from core.mission_timeline", "from core.battery_model",
            "from core.liquid_model", "from core.drone_physics",
            "from core.environment_analyzer", "from core.geometry",
        ]
        for module in [
            "core/hal_interfaces.py", "core/hal_adapters.py",
            "core/hal_telemetry.py", "core/hal_safety.py",
        ]:
            with open(module, "r") as f:
                source = f.read()
            for imp in planning_imports:
                assert imp not in source, (
                    f"HAL imports planning module in {module}: '{imp}'"
                )

    def test_planning_entrypoints_do_not_import_hal(self):
        """
        The planning-side entry points must not import HAL directly.

        HAL is reachable only through the Digital Twin runtime, which drives
        drones via the CommandSchema single entry point. The Mission Definition
        Pipeline (Planning Core + its transport) stays hardware-agnostic.
        """
        hal_imports = [
            "from core.hal_interfaces", "from core.hal_adapters",
            "from core.hal_telemetry", "from core.hal_safety",
        ]
        for module in [
            "backend/run.py",
            "backend/mission_pipeline/api.py",
            "backend/mission_pipeline/planning_core.py",
            "backend/mission_pipeline/library_api.py",
        ]:
            with open(module, "r") as f:
                source = f.read()
            for imp in hal_imports:
                assert imp not in source, (
                    f"{module} imports HAL: '{imp}'"
                )


# =========================================================================
# Cross-Layer Leak Detection (AST-Based)
# =========================================================================

class TestCrossLayerLeakDetection:
    """AST-based static analysis for forbidden cross-layer coupling."""

    def _get_imports(self, file_path: str) -> list[str]:
        """Extract all 'from X import Y' module names from a file."""
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

    def test_hal_adapters_import_isolation(self):
        imports = self._get_imports("core/hal_adapters.py")
        core_imports = [i for i in imports if i.startswith("core.")]
        for imp in core_imports:
            assert imp == "core.hal_interfaces", (
                f"hal_adapters.py leaks to {imp}"
            )

    def test_hal_telemetry_import_isolation(self):
        imports = self._get_imports("core/hal_telemetry.py")
        core_imports = [i for i in imports if i.startswith("core.")]
        for imp in core_imports:
            assert imp == "core.hal_interfaces", (
                f"hal_telemetry.py leaks to {imp}"
            )

    def test_hal_safety_import_isolation(self):
        imports = self._get_imports("core/hal_safety.py")
        core_imports = [i for i in imports if i.startswith("core.")]
        for imp in core_imports:
            assert imp == "core.hal_interfaces", (
                f"hal_safety.py leaks to {imp}"
            )

    def test_hal_interfaces_no_core_imports(self):
        imports = self._get_imports("core/hal_interfaces.py")
        core_imports = [i for i in imports if i.startswith("core.")]
        assert len(core_imports) == 0, (
            f"hal_interfaces.py has unexpected core imports: {core_imports}"
        )

    def test_ui_no_hal_imports(self):
        """The Mission Control UI must not import HAL modules."""
        for filepath, line in ui_import_lines():
            for token in ("core.hal_", "core/hal_"):
                assert token not in line, (
                    f"UI file {filepath} imports HAL: {line}"
                )

    def test_ui_no_hive_imports(self):
        """The Mission Control UI must not import Hive mutation modules."""
        hive_modules = {
            "core.hive", "core.hive_integration",
            "core.mission_orchestrator", "core.fleet_manager",
            "core.resource_system",
        }
        for filepath, line in ui_import_lines():
            for module in hive_modules:
                assert module not in line, (
                    f"UI file {filepath} imports Hive: {line}"
                )

    def test_no_global_mutable_shared_state(self):
        """HAL modules must not define module-level mutable shared state."""
        for module in [
            "core/hal_interfaces.py", "core/hal_adapters.py",
            "core/hal_telemetry.py", "core/hal_safety.py",
        ]:
            with open(module, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            if name.startswith("_") or name.isupper():
                                continue
                            if isinstance(node.value, (ast.List, ast.Set)):
                                pytest.fail(
                                    f"Module-level mutable state '{name}' "
                                    f"in {module}"
                                )

    def test_full_cross_layer_ast_scan(self):
        """Comprehensive AST scan of all HAL modules for forbidden patterns."""
        from core.hal_static_analyzer import run_full_enforcement
        result = run_full_enforcement()
        assert result.compliant, (
            f"Cross-layer leak detected: {result.summary}\n"
            + "\n".join(v.description for v in result.violations)
        )


# =========================================================================
# Contract Consistency Tests
# =========================================================================

class TestContractConsistency:
    """Verify schema identity between HAL and consuming layers."""

    def test_simulation_uses_hal_command_schema(self):
        """SimulationAdapter accepts the same CommandSchema as all adapters."""
        cmd = CommandSchema(
            command_id="test-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        sim = SimulationAdapter()
        sim.register_drone(1)
        result = sim.send_command(cmd)
        assert isinstance(result, ExecutionResult)

    def test_simulation_produces_hal_telemetry_schema(self):
        """SimulationAdapter produces TelemetrySchema identical to HAL contract."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        t = sim.get_telemetry(1)
        assert isinstance(t, TelemetrySchema)
        assert hasattr(t, "drone_id")
        assert hasattr(t, "timestamp_ms")
        assert hasattr(t, "flight_state")
        assert hasattr(t, "position")
        assert hasattr(t, "battery_pct")
        assert hasattr(t, "is_connected")
        assert hasattr(t, "raw_data")

    def test_all_adapters_produce_same_telemetry_type(self):
        """All adapters produce TelemetrySchema — same type, same fields."""
        for cls in [SimulationAdapter, PX4Adapter, ArduPilotAdapter]:
            adapter = cls()
            adapter.register_drone(1)
            t = adapter.get_telemetry(1)
            assert type(t) is TelemetrySchema
            assert type(t.flight_state) is FlightState

    def test_telemetry_frame_derived_from_hal_schema(self):
        """DroneTelemetryFrame is produced from TelemetrySchema normalization."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        proc = TelemetryStreamProcessor(sim)
        proc.register_drone(1)
        frame = proc.read_frame(1)
        assert isinstance(frame, DroneTelemetryFrame)
        assert isinstance(frame.task_state, TaskState)
        assert isinstance(frame.gps_fix_quality, GPSFixQuality)

    def test_fleet_snapshot_aggregates_frames(self):
        """FleetTelemetrySnapshot aggregates DroneTelemetryFrame objects."""
        sim = SimulationAdapter()
        for i in range(1, 4):
            sim.register_drone(i)
        proc = TelemetryStreamProcessor(sim)
        for i in range(1, 4):
            proc.register_drone(i)
        snap = proc.build_fleet_snapshot()
        assert isinstance(snap, FleetTelemetrySnapshot)
        assert snap.total_drones == 3
        assert len(snap.frames) == 3
        for frame in snap.frames:
            assert isinstance(frame, DroneTelemetryFrame)

    def test_safety_uses_hal_command_schema(self):
        """SafetyCommandRelay produces CommandSchema via FailSafeStateMapper."""
        mapper = FailSafeStateMapper()
        for fs in FailSafeState:
            cmd = mapper.map_to_command(1, fs, f"test-{fs.value}")
            assert isinstance(cmd, CommandSchema)
            assert isinstance(cmd.command_type, CommandType)

    def test_emergency_signal_from_hal_telemetry(self):
        """EmergencySignalHandler consumes TelemetrySchema directly."""
        handler = EmergencySignalHandler()
        t = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=3.0, is_connected=False,
        )
        signals = handler.check_telemetry(t)
        assert len(signals) >= 1
        for sig in signals:
            assert isinstance(sig.emergency_type, EmergencyType)

    def test_command_schema_identity_across_adapters(self):
        """Same CommandSchema accepted by all 3 adapters without modification."""
        cmd = CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "altitude_m": 15.0},
        )
        for cls in [SimulationAdapter, PX4Adapter, ArduPilotAdapter]:
            adapter = cls()
            adapter.register_drone(1)
            result = adapter.send_command(cmd)
            assert isinstance(result, ExecutionResult)
            assert result.command_id == "goto-1"
            assert result.drone_id == 1

    def test_execution_result_type_consistency(self):
        """All adapters return ExecutionResult with same type structure."""
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        for cls in [SimulationAdapter, PX4Adapter, ArduPilotAdapter]:
            adapter = cls()
            adapter.register_drone(1)
            result = adapter.send_command(cmd)
            assert type(result) is ExecutionResult
            assert type(result.status) is ExecutionStatus

    def test_flight_state_to_task_mapping_covers_all(self):
        """Every FlightState maps to exactly one TaskState."""
        mapped_states = set(FLIGHT_STATE_TO_TASK.keys())
        all_states = set(FlightState)
        assert mapped_states == all_states


# =========================================================================
# Simulation Layer Contract (SLC) Enforcement
# =========================================================================

class TestSimulationLayerContract:
    """Verify SLC rules are enforced."""

    def test_slc_schema_mirroring(self):
        """SimulationAdapter uses exact HAL schemas — no extensions."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        result = sim.send_command(cmd)
        assert type(result) is ExecutionResult
        t = sim.get_telemetry(1)
        assert type(t) is TelemetrySchema

    def test_slc_read_only_telemetry(self):
        """Simulation telemetry is a snapshot — no write methods."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        t = sim.get_telemetry(1)
        assert not hasattr(t, "write")
        assert not hasattr(t, "save")
        assert not hasattr(t, "push")
        assert not hasattr(t, "send")
        assert not hasattr(t, "modify_hive")

    def test_slc_no_decision_making(self):
        """SimulationAdapter has no decision-making methods."""
        forbidden = [
            "decide", "choose", "select_best", "optimize",
            "plan", "schedule", "allocate", "prioritize",
        ]
        with open("core/hal_adapters.py", "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pat in forbidden:
                    assert pat not in name, (
                        f"SimulationAdapter has decision method: {node.name}"
                    )

    def test_slc_import_boundaries(self):
        """hal_adapters.py imports only from hal_interfaces."""
        with open("core/hal_adapters.py", "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("core."):
                    assert node.module == "core.hal_interfaces", (
                        f"SLC violation: imports {node.module}"
                    )


# =========================================================================
# IoV Communication Contract Enforcement
# =========================================================================

class TestIoVCommunicationContract:
    """Verify IoV-C rules are enforced."""

    def test_iov_command_flow_through_schema(self):
        """All commands must flow through CommandSchema."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        cmd = CommandSchema(
            command_id="arm-1", drone_id=1,
            command_type=CommandType.ARM,
        )
        result = sim.send_command(cmd)
        assert result.status == ExecutionStatus.SUCCESS

    def test_iov_telemetry_flow_through_schema(self):
        """All telemetry flows through TelemetrySchema → DroneTelemetryFrame."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        proc = TelemetryStreamProcessor(sim)
        proc.register_drone(1)
        frame = proc.read_frame(1)
        assert isinstance(frame, DroneTelemetryFrame)

    def test_iov_safety_flow_through_relay(self):
        """Safety commands flow through SafetyCommandRelay."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        sim.arm(1)
        sim.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))
        relay = SafetyCommandRelay(sim)
        result = relay.emergency_stop(1)
        assert result.execution_result.status == ExecutionStatus.SUCCESS

    def test_iov_no_direct_cross_layer_calls(self):
        """No HAL module calls Hive or planning functions directly."""
        for module in [
            "core/hal_adapters.py", "core/hal_telemetry.py",
            "core/hal_safety.py",
        ]:
            with open(module, "r") as f:
                source = f.read()
            direct_calls = [
                "HiveController(", "MissionOrchestrator(",
                "FleetManager(", "ResourceStateTracker(",
                "plan_swarm(", "plan_routes(", "evaluate_risks(",
            ]
            for call in direct_calls:
                assert call not in source, (
                    f"Direct cross-layer call '{call}' in {module}"
                )

    def test_iov_simulation_uses_same_path(self):
        """Simulation telemetry flows through same normalization as real hardware."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        px4 = PX4Adapter()
        px4.register_drone(1)

        proc_sim = TelemetryStreamProcessor(sim)
        proc_sim.register_drone(1)
        proc_px4 = TelemetryStreamProcessor(px4)
        proc_px4.register_drone(1)

        frame_sim = proc_sim.read_frame(1)
        frame_px4 = proc_px4.read_frame(1)

        assert type(frame_sim) is type(frame_px4) is DroneTelemetryFrame
        assert type(frame_sim.task_state) is type(frame_px4.task_state) is TaskState


# =========================================================================
# Digital Twin Contract Enforcement
# =========================================================================

class TestDigitalTwinContract:
    """Verify DTC rules are enforced."""

    def test_dtc_telemetry_is_read_only(self):
        """Telemetry frames are data snapshots with no mutation methods."""
        frame = DroneTelemetryFrame(
            drone_id=1,
            position=GPSPosition(40.0, -3.0, 15.0),
            velocity=__import__("core.hal_telemetry", fromlist=["Velocity3D"]).Velocity3D(),
            heading_deg=0.0,
            battery_level_pct=100.0,
            power_draw_w=0.0,
            mission_id=None,
            task_state=TaskState.IDLE,
            gps_fix_quality=GPSFixQuality.NO_FIX,
            signal_strength_pct=0.0,
            timestamp_ms=0,
        )
        assert not hasattr(frame, "write")
        assert not hasattr(frame, "send_command")
        assert not hasattr(frame, "modify_hive")
        assert not hasattr(frame, "emit")

    def test_dtc_fleet_snapshot_is_read_only(self):
        """FleetTelemetrySnapshot is read-only aggregation."""
        snap = FleetTelemetrySnapshot(
            total_drones=3, active_drones=1, idle_drones=2,
            charging_drones=0, faulty_drones=0,
            global_timestamp_ms=1000,
        )
        assert not hasattr(snap, "send_command")
        assert not hasattr(snap, "modify_state")
        assert not hasattr(snap, "decide")

    def test_dtc_schema_consistency(self):
        """Digital Twin consumes HAL telemetry schemas without modification."""
        sim = SimulationAdapter()
        sim.register_drone(1)
        proc = TelemetryStreamProcessor(sim)
        proc.register_drone(1)

        frame = proc.read_frame(1)
        required_fields = {
            "drone_id", "position", "velocity", "heading_deg",
            "battery_level_pct", "power_draw_w", "mission_id",
            "task_state", "gps_fix_quality", "signal_strength_pct",
            "timestamp_ms",
        }
        actual_fields = {f.name for f in DroneTelemetryFrame.__dataclass_fields__.values()}
        assert required_fields.issubset(actual_fields)

    def test_dtc_no_command_emission_in_telemetry(self):
        """Telemetry module has no send_command or relay methods."""
        with open("core/hal_telemetry.py", "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                assert "send_command" not in name
                assert "relay" not in name
                assert "emit_command" not in name

    def test_dtc_ui_reads_planning_output_only(self):
        """
        The UI consumes planning/runtime output over HTTP only.

        It is a separate Next.js application, so it cannot import any Python
        module: reaching the backend at all requires the transport layer.
        """
        for filepath, line in ui_import_lines():
            assert "core." not in line, (
                f"UI {filepath} imports a backend Python module directly: {line}"
            )
