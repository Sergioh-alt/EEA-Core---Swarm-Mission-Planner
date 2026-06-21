# Phase 7 — Intelligence Layer: Architecture Proposal

**Status:** DESIGN ONLY — No implementation until explicit approval
**Date:** 2026-06-21
**Prerequisite:** Phase 6 (Realism Layer) completed and validated

---

## 1. Objective

Introduce adaptive swarm behavior while preserving deterministic planning. The Intelligence Layer sits above the existing pipeline and reacts to mission state changes — it does not replace or modify the core planning modules.

---

## 2. Architecture Overview

```
                          ┌─────────────────────────┐
                          │   Swarm State Manager    │
                          │  (new: core/swarm_state) │
                          └──────────┬──────────────┘
                                     │ monitors
                    ┌────────────────┼────────────────┐
                    │                │                 │
             ┌──────┴──────┐  ┌─────┴──────┐  ┌──────┴───────┐
             │ Drone State │  │ Mission    │  │ Failure      │
             │ Registry    │  │ Progress   │  │ Detector     │
             └──────┬──────┘  └─────┬──────┘  └──────┬───────┘
                    │               │                 │
                    └───────────────┼─────────────────┘
                                    │ triggers
                    ┌───────────────┼───────────────┐
                    │               │               │
             ┌──────┴──────┐ ┌─────┴─────┐  ┌─────┴──────┐
             │ Reallocation│ │ Mission   │  │ Swarm      │
             │ Engine      │ │ Adapter   │  │ Optimizer  │
             └──────┬──────┘ └─────┬─────┘  └─────┬──────┘
                    │              │               │
                    └──────────────┼───────────────┘
                                   │ calls
                    ┌──────────────┼──────────────┐
                    │              │              │
              plan_swarm()  plan_routes()  generate_timeline()
              (existing)    (existing)     (existing)
```

---

## 3. New Modules

### 3.1 `core/swarm_state.py` — Swarm State Manager

Central state registry for all drones and the mission.

```python
@dataclass
class DroneState:
    drone_id: int
    status: DroneStatus          # IDLE, ACTIVE, RETURNING, FAILED, SWAPPED
    current_sector_id: int
    battery_remaining_pct: float
    liquid_remaining_l: float
    position: tuple[float, float]
    flight_time_elapsed_min: float
    passes_completed: int
    passes_total: int

class DroneStatus(Enum):
    IDLE = "idle"
    LAUNCHING = "launching"
    ACTIVE = "active"
    REFILLING = "refilling"
    SWAPPING_BATTERY = "swapping_battery"
    RETURNING = "returning"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class MissionState:
    status: MissionStatus        # PLANNING, ACTIVE, PAUSED, COMPLETING, DONE, ABORTED
    start_time_min: float
    elapsed_min: float
    drones: list[DroneState]
    sectors_completed: list[int]
    sectors_remaining: list[int]
    coverage_pct: float
    active_alerts: list[str]

class SwarmStateManager:
    def __init__(self, profile: MissionProfile, swarm: SwarmPlan, routes: RoutePlan):
        ...

    def get_state(self) -> MissionState:
        ...

    def update_drone(self, drone_id: int, **kwargs) -> None:
        ...

    def mark_drone_failed(self, drone_id: int, reason: str) -> FailureEvent:
        ...

    def get_available_drones(self) -> list[DroneState]:
        ...

    def get_failed_drones(self) -> list[DroneState]:
        ...
```

**Consumers:** Reallocation Engine, Mission Adapter, UI (future Phase 7 dashboard)
**Dependencies:** `MissionProfile`, `SwarmPlan`, `RoutePlan` (all existing)

### 3.2 `core/reallocation_engine.py` — Dynamic Drone Reallocation

Handles drone failure recovery and sector reassignment.

```python
@dataclass
class ReallocationPlan:
    failed_drone_id: int
    reason: str
    reassignments: list[SectorReassignment]
    coverage_before_pct: float
    coverage_after_pct: float
    time_penalty_min: float

@dataclass
class SectorReassignment:
    sector_id: int
    from_drone_id: int
    to_drone_id: int
    additional_distance_m: float
    additional_time_min: float

def reallocate_on_failure(
    state: MissionState,
    failed_drone_id: int,
    profile: MissionProfile,
    swarm: SwarmPlan,
    assessment: EnvironmentAssessment,
) -> ReallocationPlan:
    """
    Reassign the failed drone's remaining work to available drones.

    Strategy:
    1. Identify uncompleted passes in the failed drone's sector
    2. Find available drones sorted by (proximity, remaining_capacity)
    3. Split remaining work among available drones
    4. Recompute routes for affected drones using plan_routes()
    5. Recompute timelines using generate_timeline()
    """
    ...
```

**Key design decisions:**
- Reallocation calls `plan_routes()` and `generate_timeline()` to recompute — no duplicate planning logic
- Strategy is greedy (nearest available drone) — no optimization solver needed for Phase 7
- Coverage preservation is the primary objective (time is secondary)

### 3.3 `core/swarm_optimizer.py` — Swarm Optimization Layer

Multi-objective optimization for mission planning.

```python
@dataclass
class OptimizationObjective:
    name: str                    # "time", "battery", "coverage", "balance"
    weight: float                # 0.0 - 1.0
    direction: str               # "minimize" or "maximize"

@dataclass
class OptimizationResult:
    original_plan: SwarmPlan
    optimized_plan: SwarmPlan
    improvements: dict[str, float]  # {objective_name: improvement_pct}
    iterations: int
    converged: bool

def optimize_swarm(
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
    objectives: list[OptimizationObjective],
    max_iterations: int = 50,
) -> OptimizationResult:
    """
    Iteratively adjust sector boundaries and drone assignments
    to improve multi-objective score.

    Algorithm: Hill-climbing with strip width adjustment
    - Evaluate: score = sum(weight * normalize(objective))
    - Perturb: shift strip boundaries by ±5% of strip width
    - Accept: if score improves
    - Converge: if no improvement for 5 consecutive iterations
    """
    ...
```

**Key design decisions:**
- Uses deterministic hill-climbing (no randomness, no ML)
- Perturbs existing `plan_swarm()` + `plan_routes()` outputs — reuses pipeline
- Scoring function is explicit and explainable
- Default weights: time=0.3, battery=0.3, coverage=0.2, balance=0.2

### 3.4 `core/mission_adapter.py` — Mission Adaptation

Handles mid-mission condition changes.

```python
@dataclass
class AdaptationTrigger:
    trigger_type: str    # "wind_change", "resource_depletion", "partial_completion"
    timestamp_min: float
    details: dict

@dataclass
class AdaptationResult:
    trigger: AdaptationTrigger
    action: str              # "continue", "modify", "abort"
    modified_plan: SwarmPlan | None
    modified_routes: RoutePlan | None
    modified_timeline: MissionTimeline | None
    explanation: str

def adapt_mission(
    state: MissionState,
    trigger: AdaptationTrigger,
    profile: MissionProfile,
    assessment: EnvironmentAssessment,
) -> AdaptationResult:
    """
    Evaluate and respond to mission state changes.

    Wind change: recalculate effective speed + battery → may trigger NO-GO
    Resource depletion: recalculate remaining capacity → may trigger early return
    Partial completion: replan remaining sectors only
    """
    ...
```

**Key design decisions:**
- Adaptation calls existing pipeline functions (`analyze_environment`, `plan_swarm`, `plan_routes`, `generate_timeline`)
- NO autonomous decision-making: adaptation produces a recommendation that the operator approves
- Wind threshold changes use the same `weather_thresholds` from `config/settings.py`

---

## 4. Data Flow

```
User Input → MissionProfile → Pipeline (Phases 0-6)
                                    ↓
                              SwarmPlan + RoutePlan + Timeline
                                    ↓
                           SwarmStateManager.init()
                                    ↓
                              MissionState
                                    ↓
                    ┌───────────────┼───────────────┐
                    │               │               │
              [Drone Failure]  [Wind Change]  [Optimization Request]
                    │               │               │
              reallocate()    adapt_mission()  optimize_swarm()
                    │               │               │
                    └───────────────┼───────────────┘
                                    ↓
                         Modified Plan + Timeline
                                    ↓
                            UI Update (Future)
```

---

## 5. Integration Points

### With existing modules (no modification needed):

| Existing Module | Integration | Direction |
|---|---|---|
| `plan_swarm()` | Optimizer perturbs strip widths, calls `plan_swarm()` | Consumer |
| `plan_routes()` | Reallocation recomputes routes for reassigned sectors | Consumer |
| `generate_timeline()` | All Phase 7 modules regenerate timelines after changes | Consumer |
| `analyze_environment()` | Adapter re-evaluates conditions on wind change | Consumer |
| `evaluate_risks()` | Adapter re-evaluates risk after adaptation | Consumer |
| `PhysicsConfig` | State manager uses physics constants for capacity estimates | Consumer |

### New integration (app.py changes):

```python
# After existing pipeline
from core.swarm_state import SwarmStateManager
state_manager = SwarmStateManager(profile, swarm, routes)

# Available in UI for Phase 7 dashboard (future tab)
mission_state = state_manager.get_state()
```

---

## 6. Validation Strategy

### Unit tests (per module):
- `test_swarm_state.py`: State transitions (IDLE→ACTIVE→COMPLETED, ACTIVE→FAILED)
- `test_reallocation.py`: Failure recovery produces valid plans, coverage preserved
- `test_optimizer.py`: Optimization converges, result improves score
- `test_adapter.py`: Wind change triggers recalculation, abort on NO-GO conditions

### Integration tests:
- Full pipeline → State Manager → Failure → Reallocation → New Timeline
- Full pipeline → State Manager → Wind Change → Adaptation → Modified Plan
- Full pipeline → Optimization → Improved Plan (score comparison)

### Regression tests:
- All 44 existing tests must continue to pass
- Default scenario (50ha wheat) unchanged when no adaptation/optimization triggered
- Phase 7 modules are opt-in — pipeline produces identical output when they are not invoked

---

## 7. Regression Strategy

Phase 7 follows the same additive pattern as Phase 6:

1. **No existing module modifications** — Phase 7 modules consume existing functions, never modify them
2. **Opt-in activation** — State manager and optimization are only instantiated when explicitly called
3. **Pipeline independence** — The 7-module pipeline (Intake → Environment → Swarm → Route → Resource → Risk → Decision) remains untouched
4. **Test isolation** — Phase 7 tests are in separate test files, existing test files are never modified

### Regression gates (must pass before any merge):

```
pytest tests/test_regression.py -v    # 16 v0.1/v0.2 regression tests
pytest tests/test_realism.py -v       # 28 Phase 6 realism tests
pytest tests/test_phase7_*.py -v      # New Phase 7 tests
```

---

## 8. Implementation Phases (Suggested)

| Step | Component | Scope | Depends On |
|---|---|---|---|
| 7.1 | `SwarmStateManager` | State tracking only | None |
| 7.2 | `ReallocationEngine` | Failure recovery | 7.1 |
| 7.3 | `MissionAdapter` | Wind/resource adaptation | 7.1 |
| 7.4 | `SwarmOptimizer` | Multi-objective optimization | 7.1 |
| 7.5 | Validation & Testing | Full regression + integration | 7.1-7.4 |

Each step can be validated independently before proceeding to the next.

---

## 9. Explicitly Deferred (NOT Phase 7)

- ROS2/MQTT/telemetry integration (Phase 9+)
- Hardware abstraction layer (Phase 9)
- Multi-mission Hive orchestration (Phase 8)
- Real-time sensor fusion (Phase 10)
- Voronoi partition (advanced geometry)
- Machine learning / reinforcement learning
- Autonomous merge/split drone formations

---

## 10. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Optimizer non-convergence | Medium | Low | Bounded iterations + timeout → return original plan |
| Reallocation produces worse coverage | Low | Medium | Coverage-first strategy; reject if coverage drops >5% |
| State manager adds memory overhead | Low | Low | Lightweight dataclasses, no persistence |
| Circular imports (new modules import existing) | Low | Medium | All imports are one-directional (Phase 7 → existing pipeline) |
| Phase 7 accidentally modifies pipeline behavior | Low | Critical | Additive-only architecture; regression gate enforced |
