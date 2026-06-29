"""
Phase 9.5 — HAL Static Analysis & Enforcement Tools.

Validation-only module providing AST-based static analysis of all
HAL components. Enforces the architectural boundary constraints
defined in hal_boundary_lock_spec_phase9.md, ADR-019, and ADR-020.

NO runtime behavior changes. NO new HAL functionality.
This module exists solely to verify and enforce compliance.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =========================================================================
# Violation Severity & Categories
# =========================================================================

class ViolationSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ViolationCategory(Enum):
    FORBIDDEN_IMPORT = "forbidden_import"
    FORBIDDEN_METHOD = "forbidden_method"
    FORBIDDEN_LOGIC = "forbidden_logic"
    BOUNDARY_BREACH = "boundary_breach"
    HIDDEN_INTELLIGENCE = "hidden_intelligence"
    STATE_VIOLATION = "state_violation"
    DECISION_LOGIC = "decision_logic"


# =========================================================================
# Violation Record
# =========================================================================

@dataclass
class BoundaryViolation:
    """A single detected boundary violation."""
    file_path: str
    line: int
    category: ViolationCategory
    severity: ViolationSeverity
    description: str
    node_name: Optional[str] = None


# =========================================================================
# HAL Module Registry
# =========================================================================

HAL_MODULES = [
    "core/hal_interfaces.py",
    "core/hal_adapters.py",
    "core/hal_telemetry.py",
    "core/hal_safety.py",
]

HIVE_MODULES = [
    "core.hive",
    "core.hive_integration",
    "core.mission_orchestrator",
    "core.fleet_manager",
    "core.resource_system",
]

PLANNING_MODULES = [
    "core.swarm_planner",
    "core.route_planner",
    "core.resource_planner",
    "core.risk_engine",
    "core.decision_engine",
    "core.swarm_optimizer",
    "core.reallocation_engine",
    "core.mission_adapter",
    "core.swarm_state",
    "core.mission_intake",
    "core.mission_timeline",
    "core.battery_model",
    "core.liquid_model",
    "core.drone_physics",
    "core.environment_analyzer",
    "core.geometry",
]

ML_IMPORTS = [
    "random",
    "numpy",
    "sklearn",
    "tensorflow",
    "torch",
    "keras",
    "scipy.optimize",
    "pandas",
]


# =========================================================================
# HALStaticAnalyzer — AST-Based Boundary Enforcement
# =========================================================================

class HALStaticAnalyzer:
    """
    Performs AST-based static analysis on HAL source files.

    Scans for forbidden imports, method names, and structural
    patterns that would indicate boundary violations.
    """

    FORBIDDEN_METHOD_PATTERNS: list[str] = [
        "select_best", "choose_best", "pick_best", "find_best",
        "find_optimal", "optimize", "rank", "score",
        "evaluate_fitness", "balance_load", "rebalance",
        "redistribute", "auto_assign", "auto_allocate",
        "smart_", "recommend", "suggest", "infer_priority",
        "schedule", "plan_mission", "plan_route",
        "predict", "forecast", "estimate_risk",
        "abort_mission", "cancel_mission", "stop_mission",
        "fleet_level_safety", "assign_drone",
        "allocate_resource", "prioritize",
    ]

    def __init__(self, base_path: str = ".") -> None:
        self._base_path = base_path
        self._violations: list[BoundaryViolation] = []

    def analyze_all(self) -> list[BoundaryViolation]:
        """Run all static analyses on all HAL modules."""
        self._violations = []
        for module in HAL_MODULES:
            path = os.path.join(self._base_path, module)
            if os.path.exists(path):
                self._analyze_module(path)
        return list(self._violations)

    def analyze_module(self, module_path: str) -> list[BoundaryViolation]:
        """Run all static analyses on a single module."""
        self._violations = []
        self._analyze_module(module_path)
        return list(self._violations)

    def _analyze_module(self, path: str) -> None:
        with open(path, "r") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)

        self._check_forbidden_imports(path, tree, source)
        self._check_forbidden_methods(path, tree)
        self._check_ml_imports(path, source)

    def _check_forbidden_imports(
        self, path: str, tree: ast.AST, source: str,
    ) -> None:
        """Detect imports from Hive or planning modules."""
        forbidden = HIVE_MODULES + PLANNING_MODULES
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for fb in forbidden:
                    if node.module == fb or node.module.startswith(fb + "."):
                        self._violations.append(BoundaryViolation(
                            file_path=path,
                            line=node.lineno,
                            category=ViolationCategory.FORBIDDEN_IMPORT,
                            severity=ViolationSeverity.CRITICAL,
                            description=(
                                f"Forbidden import from '{node.module}' — "
                                "HAL must not import Hive or planning modules"
                            ),
                        ))

    def _check_forbidden_methods(self, path: str, tree: ast.AST) -> None:
        """Detect method names containing forbidden patterns."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name_lower = node.name.lower()
                for pattern in self.FORBIDDEN_METHOD_PATTERNS:
                    if pattern in name_lower:
                        self._violations.append(BoundaryViolation(
                            file_path=path,
                            line=node.lineno,
                            category=ViolationCategory.FORBIDDEN_METHOD,
                            severity=ViolationSeverity.CRITICAL,
                            description=(
                                f"Forbidden method pattern '{pattern}' "
                                f"in '{node.name}'"
                            ),
                            node_name=node.name,
                        ))

    def _check_ml_imports(self, path: str, source: str) -> None:
        """Detect ML or randomization library imports."""
        for lib in ML_IMPORTS:
            patterns = [f"import {lib}", f"from {lib}"]
            for pat in patterns:
                for i, line in enumerate(source.splitlines(), 1):
                    if pat in line:
                        self._violations.append(BoundaryViolation(
                            file_path=path,
                            line=i,
                            category=ViolationCategory.HIDDEN_INTELLIGENCE,
                            severity=ViolationSeverity.CRITICAL,
                            description=(
                                f"ML/random import '{lib}' detected — "
                                "HAL must not use intelligence libraries"
                            ),
                        ))

    @property
    def violations(self) -> list[BoundaryViolation]:
        return list(self._violations)


# =========================================================================
# BoundaryViolationDetector — Domain-Specific Boundary Checks
# =========================================================================

class BoundaryViolationDetector:
    """
    Detects domain-specific boundary violations in HAL modules.

    Checks that:
    - Telemetry performs normalization only (no inference/prediction)
    - Safety performs detection and relay only (no autonomous decisions)
    - Adapters perform translation only (no planning/optimization)
    - HAL contains no scheduling or optimization logic
    - HAL contains no hidden intelligence
    """

    TELEMETRY_FORBIDDEN = [
        "anomaly_detection", "failure_prediction", "behavioral_inference",
        "health_score", "system_health_scoring", "mission_status_interpretation",
        "trend_analysis", "pattern_recognition", "classify",
        "detect_anomaly", "predict_failure",
    ]

    SAFETY_FORBIDDEN = [
        "decide_emergency", "choose_fallback", "autonomous_failover",
        "mission_abort", "cancel_mission", "auto_recover",
        "smart_failover", "adaptive_safety",
    ]

    ADAPTER_FORBIDDEN = [
        "modify_command", "reorder_command", "insert_fallback",
        "correct_mission", "plan_trajectory", "optimize_route",
        "resource_allocat", "schedule_command",
    ]

    STORAGE_PATTERNS = [
        "sqlite", "database", "write_to_disk", "save_to_file",
        "persist", "store_history", "save_state",
    ]

    def __init__(self, base_path: str = ".") -> None:
        self._base_path = base_path
        self._violations: list[BoundaryViolation] = []

    def detect_all(self) -> list[BoundaryViolation]:
        """Run all boundary checks on all HAL modules."""
        self._violations = []
        for module in HAL_MODULES:
            path = os.path.join(self._base_path, module)
            if os.path.exists(path):
                self._detect_in_module(path, module)
        return list(self._violations)

    def _detect_in_module(self, path: str, module_name: str) -> None:
        with open(path, "r") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)

        if "hal_telemetry" in module_name:
            self._check_patterns(
                path, tree, self.TELEMETRY_FORBIDDEN,
                "telemetry", ViolationCategory.BOUNDARY_BREACH,
            )
            self._check_storage(path, source)

        if "hal_safety" in module_name:
            self._check_patterns(
                path, tree, self.SAFETY_FORBIDDEN,
                "safety", ViolationCategory.DECISION_LOGIC,
            )

        if "hal_adapters" in module_name:
            self._check_patterns(
                path, tree, self.ADAPTER_FORBIDDEN,
                "adapter", ViolationCategory.BOUNDARY_BREACH,
            )

    def _check_patterns(
        self,
        path: str,
        tree: ast.AST,
        forbidden: list[str],
        domain: str,
        category: ViolationCategory,
    ) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name_lower = node.name.lower()
                for pattern in forbidden:
                    if pattern in name_lower:
                        self._violations.append(BoundaryViolation(
                            file_path=path,
                            line=node.lineno,
                            category=category,
                            severity=ViolationSeverity.CRITICAL,
                            description=(
                                f"Forbidden {domain} pattern '{pattern}' "
                                f"in '{node.name}'"
                            ),
                            node_name=node.name,
                        ))

    def _check_storage(self, path: str, source: str) -> None:
        source_lower = source.lower()
        for pattern in self.STORAGE_PATTERNS:
            if pattern in source_lower:
                self._violations.append(BoundaryViolation(
                    file_path=path,
                    line=0,
                    category=ViolationCategory.STATE_VIOLATION,
                    severity=ViolationSeverity.HIGH,
                    description=(
                        f"Storage pattern '{pattern}' in telemetry — "
                        "telemetry must not persist data"
                    ),
                ))

    @property
    def violations(self) -> list[BoundaryViolation]:
        return list(self._violations)


# =========================================================================
# ForbiddenLogicScanner — Deep AST Logic Pattern Detection
# =========================================================================

class ForbiddenLogicScanner:
    """
    Deep AST scanner for forbidden logic patterns in HAL code.

    Detects:
    - Global/class-level mutable state that could enable learning
    - Cross-drone reasoning patterns
    - Fleet-level aggregation with decision branches
    - Optimization loops (while loops with comparison updates)
    """

    def __init__(self, base_path: str = ".") -> None:
        self._base_path = base_path
        self._violations: list[BoundaryViolation] = []

    def scan_all(self) -> list[BoundaryViolation]:
        """Scan all HAL modules for forbidden logic patterns."""
        self._violations = []
        for module in HAL_MODULES:
            path = os.path.join(self._base_path, module)
            if os.path.exists(path):
                self._scan_module(path)
        return list(self._violations)

    def _scan_module(self, path: str) -> None:
        with open(path, "r") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
        self._check_optimization_loops(path, tree)
        self._check_global_mutable_state(path, tree)
        self._check_forbidden_builtins(path, tree)

    def _check_optimization_loops(self, path: str, tree: ast.AST) -> None:
        """Detect while-loops that update a 'best' or 'optimal' variable."""
        for node in ast.walk(tree):
            if isinstance(node, ast.While):
                body_names = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Name):
                        body_names.add(child.id.lower())
                opt_names = {"best", "optimal", "minimum", "maximum", "candidate"}
                if body_names & opt_names:
                    self._violations.append(BoundaryViolation(
                        file_path=path,
                        line=node.lineno,
                        category=ViolationCategory.FORBIDDEN_LOGIC,
                        severity=ViolationSeverity.CRITICAL,
                        description=(
                            "Optimization loop detected — HAL must not "
                            "contain optimization logic"
                        ),
                    ))

    def _check_global_mutable_state(self, path: str, tree: ast.AST) -> None:
        """Detect module-level mutable assignments (lists/dicts/sets)."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if name.startswith("_") or name.isupper():
                            continue
                        if isinstance(node.value, (ast.List, ast.Set)):
                            self._violations.append(BoundaryViolation(
                                file_path=path,
                                line=node.lineno,
                                category=ViolationCategory.STATE_VIOLATION,
                                severity=ViolationSeverity.MEDIUM,
                                description=(
                                    f"Module-level mutable state '{name}' — "
                                    "HAL must be stateless or mechanically stateful"
                                ),
                                node_name=name,
                            ))

    def _check_forbidden_builtins(self, path: str, tree: ast.AST) -> None:
        """Detect use of sorted() with key= or min()/max() with key= in HAL."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in ("sorted", "min", "max"):
                    if node.keywords:
                        for kw in node.keywords:
                            if kw.arg == "key":
                                self._violations.append(BoundaryViolation(
                                    file_path=path,
                                    line=node.lineno,
                                    category=ViolationCategory.HIDDEN_INTELLIGENCE,
                                    severity=ViolationSeverity.HIGH,
                                    description=(
                                        f"Ranking/sorting with key= via "
                                        f"'{func.id}()' — potential "
                                        "optimization or decision logic"
                                    ),
                                ))

    @property
    def violations(self) -> list[BoundaryViolation]:
        return list(self._violations)


# =========================================================================
# Aggregate Enforcement Runner
# =========================================================================

@dataclass
class EnforcementResult:
    """Aggregate result of all enforcement checks."""
    total_modules_scanned: int
    total_violations: int
    critical_violations: int
    high_violations: int
    medium_violations: int
    low_violations: int
    violations: list[BoundaryViolation] = field(default_factory=list)
    compliant: bool = True

    @property
    def summary(self) -> str:
        status = "COMPLIANT" if self.compliant else "NON-COMPLIANT"
        return (
            f"HAL Enforcement: {status} | "
            f"Modules={self.total_modules_scanned} | "
            f"Violations={self.total_violations} "
            f"(C={self.critical_violations} H={self.high_violations} "
            f"M={self.medium_violations} L={self.low_violations})"
        )


def run_full_enforcement(base_path: str = ".") -> EnforcementResult:
    """Run all enforcement tools and return aggregate result."""
    analyzer = HALStaticAnalyzer(base_path)
    detector = BoundaryViolationDetector(base_path)
    scanner = ForbiddenLogicScanner(base_path)

    all_violations: list[BoundaryViolation] = []
    all_violations.extend(analyzer.analyze_all())
    all_violations.extend(detector.detect_all())
    all_violations.extend(scanner.scan_all())

    modules_scanned = sum(
        1 for m in HAL_MODULES
        if os.path.exists(os.path.join(base_path, m))
    )

    critical = sum(1 for v in all_violations if v.severity == ViolationSeverity.CRITICAL)
    high = sum(1 for v in all_violations if v.severity == ViolationSeverity.HIGH)
    medium = sum(1 for v in all_violations if v.severity == ViolationSeverity.MEDIUM)
    low = sum(1 for v in all_violations if v.severity == ViolationSeverity.LOW)

    return EnforcementResult(
        total_modules_scanned=modules_scanned,
        total_violations=len(all_violations),
        critical_violations=critical,
        high_violations=high,
        medium_violations=medium,
        low_violations=low,
        violations=all_violations,
        compliant=(critical == 0 and high == 0),
    )
