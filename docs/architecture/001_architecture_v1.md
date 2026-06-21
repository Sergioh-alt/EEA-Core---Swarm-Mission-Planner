# Architecture v1 — EEA Swarm Mission Planner

## Overview

The Swarm Mission Planner follows a pipeline architecture where each module transforms and enriches the mission data before passing it downstream. This mirrors the EEA Core decision cycle: **Observe → Analyze → Plan → Decide → Recommend**.

## Module Diagram

```
User Input (Streamlit UI)
        │
        ▼
┌─────────────────┐
│  Mission Intake  │  Validate inputs, create MissionProfile
└────────┬────────┘
         ▼
┌──────────────────────┐
│ Environment Analyzer │  Assess weather, terrain, flight conditions
└────────┬─────────────┘
         ▼
┌─────────────────┐
│  Swarm Planner  │  Partition field, assign drones to sectors
└────────┬────────┘
         ▼
┌─────────────────┐
│  Route Planner  │  Generate flight paths (boustrophedon)
└────────┬────────┘
         ▼
┌──────────────────┐
│ Resource Planner │  Estimate battery, liquid, refills, duration
└────────┬─────────┘
         ▼
┌──────────────┐
│  Risk Engine │  Evaluate weather/battery/coverage/operational risks
└────────┬─────┘
         ▼
┌─────────────────┐
│ Decision Engine │  Synthesize final recommendation (GO / NO-GO)
└────────┬────────┘
         ▼
   Streamlit Dashboard
```

## Modules

### Mission Intake (`core/mission_intake.py`)

**Responsibility**: Receive raw user inputs, validate them, and produce a canonical `MissionProfile` dataclass.

- Input validation via `utils/validators.py`
- Crop profile lookup from `config/settings.py`
- Complexity multiplier calculation

**Output**: `MissionProfile`

### Environment Analyzer (`core/environment_analyzer.py`)

**Responsibility**: Evaluate field characteristics and weather conditions to determine operational feasibility.

- Area categorization (Small/Medium/Large/Industrial)
- Wind and temperature assessment against thresholds
- Flight condition determination (Clear/Caution/Restricted/No-Fly)
- Speed and spray width recommendations

**Output**: `EnvironmentAssessment`

### Swarm Planner (`core/swarm_planner.py`)

**Responsibility**: Divide the field into sectors and assign each sector to a drone.

- Grid computation based on drone count
- Field partitioning into rectangular sectors
- Workload balancing across the swarm

**Output**: `SwarmPlan` (list of `Sector` assignments)

### Route Planner (`core/route_planner.py`)

**Responsibility**: Generate flight paths within each sector.

- Boustrophedon (back-and-forth) pattern generation
- Waypoint sequencing
- Distance and time estimation
- Overlap calculation to avoid coverage gaps

**Output**: `RoutePlan` (list of `DroneRoute` with waypoints)

### Resource Planner (`core/resource_planner.py`)

**Responsibility**: Estimate resource consumption for the mission.

- Battery consumption per drone (Wh model)
- Liquid requirements based on crop spray rate
- Refill cycle calculation
- Mission duration estimation (parallel execution)
- Bottleneck identification

**Output**: `ResourcePlan`

### Risk Engine (`core/risk_engine.py`)

**Responsibility**: Evaluate risks across four categories.

- **Weather Risk**: wind speed, temperature vs. thresholds
- **Battery Risk**: consumption vs. capacity
- **Coverage Risk**: route efficiency vs. acceptable coverage
- **Operational Risk**: duration, refills, flight conditions, redundancy

Each risk produces a score (0.0–1.0), level, description, and mitigation.

**Output**: `RiskAssessment`

### Decision Engine (`core/decision_engine.py`)

**Responsibility**: Synthesize all module outputs into a final recommendation.

- Confidence calculation based on risk scores, coverage, and conditions
- Optimal drone count recommendation
- Operational notes generation
- GO / GO WITH CAUTION / NO-GO decision
- Human-readable summary

**Output**: `MissionRecommendation`

## Data Flow

All modules communicate through typed dataclasses. There are no shared mutable states or side effects — each module is a pure function of its inputs.

```
MissionProfile → EnvironmentAssessment → SwarmPlan → RoutePlan → ResourcePlan → RiskAssessment → MissionRecommendation
```

## Configuration

All constants, thresholds, and crop profiles are centralized in `config/settings.py` using dataclasses:

- `AppConfig` — application metadata
- `DroneSpec` — default drone specifications
- `WeatherThresholds` — operational weather limits
- `RiskThresholds` — risk assessment parameters
- `CROP_PROFILES` — crop-specific operational profiles

## UI Layer

The Streamlit interface (`ui/`) is separated from the core logic:

- `mission_config.py` — sidebar configuration panel
- `swarm_view.py` — sector map and route visualization (Plotly)
- `resource_dashboard.py` — battery, liquid, and timeline charts
- `risk_dashboard.py` — risk radar and detailed risk cards
- `recommendation_panel.py` — final GO/NO-GO decision display

## Design Decisions

See `/docs/decisions/` for Architecture Decision Records (ADRs).
