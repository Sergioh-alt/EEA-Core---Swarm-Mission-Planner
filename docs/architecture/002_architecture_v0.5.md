# Architecture v0.5 — Consolidated System

## System Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │              STREAMLIT UI LAYER              │
                    │                                             │
                    │  ┌─────────────┐  ┌──────────────────────┐ │
                    │  │ mission_    │  │ swarm_view.py        │ │
                    │  │ config.py   │  │  - Sector Map (poly) │ │
                    │  │  - Slider   │  │  - Route Preview     │ │
                    │  │  - Draw     │  │  - Assignment Table  │ │
                    │  │    Polygon  │  └──────────────────────┘ │
                    │  └─────────────┘  ┌──────────────────────┐ │
                    │                    │ resource_dashboard   │ │
                    │                    │ risk_dashboard       │ │
                    │                    │ recommendation_panel │ │
                    │                    └──────────────────────┘ │
                    └───────────────────────┬─────────────────────┘
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        DECISION PIPELINE (7 modules)                       │
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │ mission_     │───▶│ environment_ │───▶│ swarm_       │                │
│  │ intake.py    │    │ analyzer.py  │    │ planner.py   │                │
│  │              │    │              │    │              │                │
│  │ MissionPro-  │    │ Environment- │    │  if synthetic│                │
│  │ file         │    │ Assessment   │    │   → grid     │                │
│  │ + FieldGeo-  │    │              │    │  if polygon  │                │
│  │   metry      │    │              │    │   → strip    │                │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                │
│                                                  │                        │
│                                                  ▼                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │ decision_    │◀───│ risk_        │◀───│ resource_    │◀──┐            │
│  │ engine.py    │    │ engine.py    │    │ planner.py   │   │            │
│  │              │    │              │    │              │   │            │
│  │ GO / NO-GO / │    │ Weather +    │    │ Battery +    │   │            │
│  │ CAUTION      │    │ Battery +    │    │ Liquid +     │   │            │
│  │              │    │ Coverage +   │    │ Duration     │   │            │
│  │              │    │ Operational  │    │              │   │            │
│  └──────────────┘    └──────────────┘    └──────────────┘   │            │
│                                                              │            │
│                                           ┌──────────────┐   │            │
│                                           │ route_       │───┘            │
│                                           │ planner.py   │                │
│                                           │              │                │
│                                           │  if grid     │                │
│                                           │   → rect     │                │
│                                           │  if strip    │                │
│                                           │   → sweep    │                │
│                                           └──────────────┘                │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         FOUNDATION LAYER                                   │
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │ geometry.py  │    │ settings.py  │    │ logger.py    │                │
│  │              │    │              │    │ validators.py│                │
│  │ FieldGeometry│    │ DroneSpec    │    │              │                │
│  │ SectorGeo-   │    │ CropProfiles │    │              │                │
│  │   metry      │    │ Thresholds   │    │              │                │
│  │ compute_     │    │              │    │              │                │
│  │   polygon_   │    │              │    │              │                │
│  │   orientation│    │              │    │              │                │
│  └──────────────┘    └──────────────┘    └──────────────┘                │
│                                                                           │
│  External: shapely 2.1.2 (GEOS backend)                                  │
└───────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Input (Slider OR Polygon Points)
        │
        ▼
FieldGeometry.from_hectares()  OR  FieldGeometry.from_points()
        │                                    │
        │  is_synthetic=True                 │  is_synthetic=False
        │                                    │
        └────────────────┬───────────────────┘
                         │
                         ▼
              MissionProfile (includes FieldGeometry)
                         │
                         ▼
              EnvironmentAssessment (weather, speed, spray width)
                         │
                         ▼
              ┌──────────┴──────────┐
              │                     │
         is_synthetic?         !is_synthetic?
              │                     │
              ▼                     ▼
       Grid Partition        Strip Partition
       (v0.1 compat)         (MABR-aligned)
              │                     │
              └──────────┬──────────┘
                         │
                         ▼
                    SwarmPlan
                    (partition_method: "grid" | "strip")
                         │
                         ▼
              ┌──────────┴──────────┐
              │                     │
        grid method?          strip method?
              │                     │
              ▼                     ▼
       Rectangular Route     Polygon Sweep Route
       (fixed passes)        (intersection-based)
              │                     │
              └──────────┬──────────┘
                         │
                         ▼
                    RoutePlan → ResourcePlan → RiskAssessment → Recommendation
```

## Module Responsibilities (Post-Consolidation)

| Module | Responsibility | Geometry-Aware |
|--------|---------------|----------------|
| `core/geometry.py` | Field/sector geometry, MABR orientation | YES (owns all geometry) |
| `core/mission_intake.py` | Input validation, profile creation | Delegates to geometry |
| `core/environment_analyzer.py` | Weather/conditions assessment | NO |
| `core/swarm_planner.py` | Field partitioning, drone assignment | YES (uses geometry) |
| `core/route_planner.py` | Boustrophedon route generation | YES (uses geometry) |
| `core/resource_planner.py` | Battery, liquid, duration estimation | NO |
| `core/risk_engine.py` | Multi-factor risk evaluation | NO |
| `core/decision_engine.py` | Final GO/NO-GO recommendation | NO |

## Key Design Decisions

1. **Dual-strategy dispatch**: `is_synthetic` flag determines grid vs strip partition + rectangular vs polygon routing. Single code path, no feature flags.

2. **Geometry centralization**: All polygon operations (orientation, MABR, validation) live in `core/geometry.py`. No duplicated math across modules.

3. **Pure function pipeline**: Each module takes typed dataclass inputs, returns typed dataclass outputs. No shared state, no side effects beyond logging.

4. **Backward compatibility**: v0.1 Slider mode produces byte-identical outputs to original implementation. Zero behavioral changes for existing users.
