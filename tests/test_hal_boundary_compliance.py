"""
Phase 9.5 — HAL Boundary Compliance Tests.

Comprehensive enforcement tests verifying every HAL component
respects architectural boundaries per:
- hal_boundary_lock_spec_phase9.md
- ADR-019 (HAL Interfaces & Adapters)
- ADR-020 (HAL Telemetry & Safety)
- decision_boundary_map_phase9.md

NO new functionality tested — enforcement only.
"""

import ast
import inspect
import os

import pytest

from core.hal_static_analyzer import (
    BoundaryViolationDetector,
    ForbiddenLogicScanner,
    HALStaticAnalyzer,
    ViolationSeverity,
    run_full_enforcement,
)


# =========================================================================
# HALStaticAnalyzer Tests
# =========================================================================

class TestHALStaticAnalyzer:
    """Verify HALStaticAnalyzer detects violations correctly."""

    def test_clean_hal_modules_pass(self):
        analyzer = HALStaticAnalyzer()
        violations = analyzer.analyze_all()
        assert len(violations) == 0, (
            f"Unexpected violations: {[v.description for v in violations]}"
        )

    def test_detects_forbidden_import(self, tmp_path):
        bad = tmp_path / "bad_module.py"
        bad.write_text("from core.hive import HiveController\n")
        analyzer = HALStaticAnalyzer()
        violations = analyzer.analyze_module(str(bad))
        assert any("Forbidden import" in v.description for v in violations)

    def test_detects_forbidden_method(self, tmp_path):
        bad = tmp_path / "bad_module.py"
        bad.write_text("def optimize_route(data):\n    return data\n")
        analyzer = HALStaticAnalyzer()
        violations = analyzer.analyze_module(str(bad))
        assert any("optimize" in v.description for v in violations)

    def test_detects_ml_import(self, tmp_path):
        bad = tmp_path / "bad_module.py"
        bad.write_text("import numpy as np\n")
        analyzer = HALStaticAnalyzer()
        violations = analyzer.analyze_module(str(bad))
        assert any("numpy" in v.description for v in violations)


# =========================================================================
# BoundaryViolationDetector Tests
# =========================================================================

class TestBoundaryViolationDetector:
    """Verify domain-specific boundary detection."""

    def test_clean_hal_modules_pass(self):
        detector = BoundaryViolationDetector()
        violations = detector.detect_all()
        assert len(violations) == 0, (
            f"Unexpected violations: {[v.description for v in violations]}"
        )

    def test_detects_telemetry_inference(self, tmp_path):
        bad = tmp_path / "hal_telemetry.py"
        bad.write_text("def detect_anomaly(data):\n    return False\n")
        detector = BoundaryViolationDetector()
        detector._detect_in_module(str(bad), "hal_telemetry")
        assert any("telemetry" in v.description for v in detector.violations)

    def test_detects_safety_decision(self, tmp_path):
        bad = tmp_path / "hal_safety.py"
        bad.write_text("def decide_emergency(drone_id):\n    pass\n")
        detector = BoundaryViolationDetector()
        detector._detect_in_module(str(bad), "hal_safety")
        assert any("safety" in v.description for v in detector.violations)

    def test_detects_adapter_planning(self, tmp_path):
        bad = tmp_path / "hal_adapters.py"
        bad.write_text("def optimize_route(waypoints):\n    return waypoints\n")
        detector = BoundaryViolationDetector()
        detector._detect_in_module(str(bad), "hal_adapters")
        assert any("adapter" in v.description for v in detector.violations)


# =========================================================================
# ForbiddenLogicScanner Tests
# =========================================================================

class TestForbiddenLogicScanner:
    """Verify deep AST pattern detection."""

    def test_clean_hal_modules_pass(self):
        scanner = ForbiddenLogicScanner()
        violations = scanner.scan_all()
        assert len(violations) == 0, (
            f"Unexpected violations: {[v.description for v in violations]}"
        )

    def test_detects_optimization_loop(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text(
            "best = None\n"
            "while True:\n"
            "    candidate = next_candidate()\n"
            "    if candidate > best:\n"
            "        best = candidate\n"
            "    break\n"
        )
        scanner = ForbiddenLogicScanner()
        scanner._scan_module(str(bad))
        assert any("Optimization loop" in v.description for v in scanner.violations)

    def test_detects_sorting_with_key(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("result = sorted(items, key=lambda x: x.score)\n")
        scanner = ForbiddenLogicScanner()
        scanner._scan_module(str(bad))
        assert any("sorted" in v.description for v in scanner.violations)


# =========================================================================
# Aggregate Enforcement Tests
# =========================================================================

class TestFullEnforcement:
    """Verify aggregate enforcement runner."""

    def test_full_enforcement_passes(self):
        result = run_full_enforcement()
        assert result.compliant, (
            f"HAL is non-compliant: {result.summary}\n"
            + "\n".join(v.description for v in result.violations)
        )
        assert result.total_modules_scanned == 4
        assert result.total_violations == 0

    def test_enforcement_result_summary(self):
        result = run_full_enforcement()
        assert "COMPLIANT" in result.summary
        assert "Modules=4" in result.summary


# =========================================================================
# Telemetry Boundary Lock — Per hal_boundary_lock_spec Section 1
# =========================================================================

class TestTelemetryLock:
    """Verify telemetry performs normalization only."""

    def test_no_inference_methods(self):
        with open("core/hal_telemetry.py", "r") as f:
            tree = ast.parse(f.read())
        forbidden = [
            "infer", "predict", "forecast", "classify",
            "anomaly", "pattern", "trend", "health_score",
            "interpret", "analyze_behavior",
        ]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pat in forbidden:
                    assert pat not in name, (
                        f"Telemetry contains inference method: {node.name}"
                    )

    def test_no_prediction_logic(self):
        with open("core/hal_telemetry.py", "r") as f:
            source = f.read()
        tree = ast.parse(source)
        forbidden = [
            "predict", "forecast", "trend_analysis",
            "estimate_remaining", "will_fail",
        ]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pat in forbidden:
                    assert pat not in name, (
                        f"Telemetry contains prediction method: {node.name}"
                    )

    def test_no_storage_layer(self):
        with open("core/hal_telemetry.py", "r") as f:
            source = f.read().lower()
        storage = ["sqlite", "database", "write_to_disk", "save_to_file", "persist"]
        for pat in storage:
            assert pat not in source, (
                f"Telemetry contains storage pattern: '{pat}'"
            )

    def test_no_historical_data_structures(self):
        with open("core/hal_telemetry.py", "r") as f:
            source = f.read().lower()
        history = ["history_buffer", "time_series", "rolling_average", "window_size"]
        for pat in history:
            assert pat not in source, (
                f"Telemetry contains historical data pattern: '{pat}'"
            )

    def test_normalization_is_deterministic(self):
        """Same input always produces same output."""
        from core.hal_adapters import SimulationAdapter
        from core.hal_telemetry import TelemetryStreamProcessor
        from core.hal_interfaces import CommandSchema, CommandType

        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
            params={"altitude_m": 15.0},
        ))

        proc = TelemetryStreamProcessor(adapter)
        proc.register_drone(1, mission_id="m1")

        frame1 = proc.read_frame(1)
        frame2 = proc.read_frame(1)

        assert frame1.drone_id == frame2.drone_id
        assert frame1.position.latitude == frame2.position.latitude
        assert frame1.position.longitude == frame2.position.longitude
        assert frame1.position.altitude_m == frame2.position.altitude_m
        assert frame1.battery_level_pct == frame2.battery_level_pct
        assert frame1.task_state == frame2.task_state
        assert frame1.mission_id == frame2.mission_id


# =========================================================================
# Safety Boundary Lock — Per hal_boundary_lock_spec Section 2
# =========================================================================

class TestSafetyLock:
    """Verify safety performs detection and relay only."""

    def test_no_autonomous_decision_methods(self):
        with open("core/hal_safety.py", "r") as f:
            tree = ast.parse(f.read())
        forbidden = [
            "decide", "choose", "select", "evaluate",
            "abort_mission", "cancel_mission", "auto_recover",
            "smart_failover", "adaptive",
        ]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pat in forbidden:
                    assert pat not in name, (
                        f"Safety contains decision method: {node.name}"
                    )

    def test_no_mission_logic(self):
        with open("core/hal_safety.py", "r") as f:
            source = f.read()
        assert "abort_mission" not in source
        assert "cancel_mission" not in source
        assert "stop_mission" not in source
        assert "mission_success" not in source

    def test_failsafe_mapping_is_deterministic(self):
        """Same fail-safe state always maps to same command type."""
        from core.hal_safety import FailSafeState, FailSafeStateMapper
        from core.hal_interfaces import CommandType

        mapper = FailSafeStateMapper()
        expected = {
            FailSafeState.KILL: CommandType.EMERGENCY_STOP,
            FailSafeState.RETURN_TO_HOME: CommandType.RETURN_TO_HOME,
            FailSafeState.LAND_IN_PLACE: CommandType.LAND,
            FailSafeState.HOVER: CommandType.SET_SPEED,
            FailSafeState.DISARM: CommandType.DISARM,
        }
        for fs, expected_ct in expected.items():
            cmd = mapper.map_to_command(1, fs, f"test-{fs.value}")
            assert cmd.command_type == expected_ct

    def test_signal_handler_does_not_decide_response(self):
        """EmergencySignalHandler returns signals, not actions."""
        from core.hal_safety import EmergencySignalHandler
        from core.hal_interfaces import FlightState, TelemetrySchema

        handler = EmergencySignalHandler()
        telemetry = TelemetrySchema(
            drone_id=1, timestamp_ms=1000,
            flight_state=FlightState.IN_FLIGHT,
            battery_pct=3.0, is_connected=False,
        )
        signals = handler.check_telemetry(telemetry)
        for sig in signals:
            assert not hasattr(sig, "recommended_action")
            assert not hasattr(sig, "response")
            assert not hasattr(sig, "fail_safe")


# =========================================================================
# Adapter Boundary Lock — Per hal_boundary_lock_spec Section 3
# =========================================================================

class TestAdapterLock:
    """Verify adapters perform protocol translation only."""

    def test_no_planning_methods(self):
        with open("core/hal_adapters.py", "r") as f:
            tree = ast.parse(f.read())
        forbidden = [
            "plan", "optimize", "schedule", "allocate",
            "prioritize", "evaluate", "score", "rank",
        ]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                for pat in forbidden:
                    assert pat not in name, (
                        f"Adapter contains planning method: {node.name}"
                    )

    def test_no_command_modification(self):
        """Adapters translate, never modify command intent."""
        from core.hal_adapters import SimulationAdapter
        from core.hal_interfaces import CommandSchema, CommandType, ExecutionStatus

        adapter = SimulationAdapter()
        adapter.register_drone(1)
        adapter.arm(1)
        adapter.send_command(CommandSchema(
            command_id="takeoff-1", drone_id=1,
            command_type=CommandType.TAKEOFF,
        ))

        cmd = CommandSchema(
            command_id="goto-1", drone_id=1,
            command_type=CommandType.GOTO,
            params={"latitude": 40.0, "longitude": -3.0, "altitude_m": 15.0},
        )
        result = adapter.send_command(cmd)
        assert result.status == ExecutionStatus.SUCCESS
        assert result.telemetry.position.latitude == 40.0
        assert result.telemetry.position.longitude == -3.0

    def test_adapters_import_only_from_hal_interfaces(self):
        with open("core/hal_adapters.py", "r") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("core."):
                    assert node.module == "core.hal_interfaces", (
                        f"hal_adapters imports from {node.module} — "
                        "must only import from core.hal_interfaces"
                    )

    def test_all_adapters_implement_full_interface(self):
        from core.hal_adapters import (
            ArduPilotAdapter,
            PX4Adapter,
            SimulationAdapter,
        )
        from core.hal_interfaces import BaseDroneInterface

        required = {
            "send_command", "get_telemetry", "arm", "disarm",
            "return_to_home", "is_connected", "get_adapter_name",
        }
        for adapter_cls in [SimulationAdapter, PX4Adapter, ArduPilotAdapter]:
            assert issubclass(adapter_cls, BaseDroneInterface)
            for method in required:
                assert hasattr(adapter_cls, method), (
                    f"{adapter_cls.__name__} missing {method}"
                )


# =========================================================================
# State Lock — Per hal_boundary_lock_spec Section 4
# =========================================================================

class TestStateLock:
    """Verify HAL has no persistent cross-mission state."""

    def test_no_cross_mission_memory(self):
        """Adapters don't retain data across independent sessions."""
        from core.hal_adapters import SimulationAdapter
        from core.hal_interfaces import CommandSchema, CommandType

        adapter1 = SimulationAdapter()
        adapter1.register_drone(1)
        adapter1.arm(1)

        adapter2 = SimulationAdapter()
        adapter2.register_drone(1)
        t = adapter2.get_telemetry(1)
        assert t.flight_state.value == "grounded"

    def test_no_global_fleet_reasoning(self):
        forbidden = [
            "fleet_reasoning", "cross_drone", "global_state",
            "fleet_decision", "swarm_logic", "collective",
        ]
        for module in ["core/hal_adapters.py", "core/hal_telemetry.py", "core/hal_safety.py"]:
            with open(module, "r") as f:
                source = f.read().lower()
            for pat in forbidden:
                assert pat not in source, (
                    f"'{pat}' found in {module}"
                )

    def test_no_learning_patterns(self):
        forbidden = [
            "learn", "train", "fit", "model.predict",
            "gradient", "backprop", "neural", "weight_update",
        ]
        for module in ["core/hal_adapters.py", "core/hal_telemetry.py", "core/hal_safety.py"]:
            with open(module, "r") as f:
                source = f.read().lower()
            for pat in forbidden:
                assert pat not in source, (
                    f"Learning pattern '{pat}' in {module}"
                )


# =========================================================================
# Decision Ownership — Per hal_boundary_lock_spec Section 5
# =========================================================================

class TestDecisionOwnership:
    """Verify Hive remains the only decision authority."""

    def test_hal_does_not_assign_drones(self):
        for module in ["core/hal_adapters.py", "core/hal_telemetry.py", "core/hal_safety.py"]:
            with open(module, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                    assert "assign_drone" not in name, (
                        f"HAL assigns drones in {module}: {node.name}"
                    )

    def test_hal_does_not_allocate_resources(self):
        for module in ["core/hal_adapters.py", "core/hal_telemetry.py", "core/hal_safety.py"]:
            with open(module, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                    assert "allocate" not in name, (
                        f"HAL allocates resources in {module}: {node.name}"
                    )

    def test_hal_does_not_emit_recommendations(self):
        for module in ["core/hal_adapters.py", "core/hal_telemetry.py", "core/hal_safety.py"]:
            with open(module, "r") as f:
                source = f.read().lower()
            for pat in ["recommend", "suggest_action", "advise"]:
                assert pat not in source, (
                    f"HAL emits recommendations in {module}: '{pat}'"
                )

    def test_hal_does_not_influence_hive(self):
        """HAL modules do not import or reference Hive internals."""
        for module in [
            "core/hal_adapters.py",
            "core/hal_telemetry.py",
            "core/hal_safety.py",
        ]:
            with open(module, "r") as f:
                source = f.read()
            for hive_mod in [
                "from core.hive ",
                "from core.hive_integration ",
                "from core.mission_orchestrator ",
                "from core.fleet_manager ",
                "from core.resource_system ",
            ]:
                assert hive_mod not in source, (
                    f"HAL imports Hive module in {module}: '{hive_mod}'"
                )


# =========================================================================
# Import Isolation — Cross-Module Dependency Check
# =========================================================================

class TestImportIsolation:
    """Verify HAL modules import only from hal_interfaces."""

    def test_hal_telemetry_imports(self):
        with open("core/hal_telemetry.py", "r") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("core."):
                    assert node.module == "core.hal_interfaces", (
                        f"hal_telemetry imports from {node.module}"
                    )

    def test_hal_safety_imports(self):
        with open("core/hal_safety.py", "r") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("core."):
                    assert node.module == "core.hal_interfaces", (
                        f"hal_safety imports from {node.module}"
                    )

    def test_hal_adapters_imports(self):
        with open("core/hal_adapters.py", "r") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("core."):
                    assert node.module == "core.hal_interfaces", (
                        f"hal_adapters imports from {node.module}"
                    )

    def test_no_phase07_imports_in_any_hal_module(self):
        planning = [
            "core.swarm_planner", "core.route_planner",
            "core.resource_planner", "core.risk_engine",
            "core.decision_engine", "core.swarm_optimizer",
            "core.reallocation_engine", "core.mission_adapter",
        ]
        for module in [
            "core/hal_interfaces.py", "core/hal_adapters.py",
            "core/hal_telemetry.py", "core/hal_safety.py",
        ]:
            with open(module, "r") as f:
                source = f.read()
            for imp in planning:
                assert f"from {imp}" not in source, (
                    f"Planning import '{imp}' in {module}"
                )
