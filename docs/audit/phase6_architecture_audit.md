# Architecture Consistency Audit — Post Phase 6

**Date:** 2026-06-21
**Scope:** All Python modules (core/, ui/, utils/, config/, app.py)
**Purpose:** Pre-Phase 7 audit for duplicates, dead code, unused imports, and centralization verification

---

## 1. Duplicate Logic

### 1.1 REFILL_DURATION constant (duplicated)

| File | Constant | Value |
|---|---|---|
| `core/liquid_model.py:24` | `REFILL_DURATION_MIN` | 5.0 |
| `core/resource_planner.py:42` | `REFILL_TIME_MIN` | 5.0 |

**Impact:** Same concept, different names. `resource_planner` predates Phase 6; `liquid_model` redefines it. If one is changed and not the other, behavior diverges silently.

**Fix:** Move to `config/settings.py` as a single constant `REFILL_TIME_MIN = 5.0`. Both modules import from config.

### 1.2 BATTERY_SWAP_TIME constant (duplicated)

| File | Constant | Value |
|---|---|---|
| `core/battery_model.py:33` | `BATTERY_SWAP_TIME_MIN` | 3.0 |
| `core/resource_planner.py:43` | `BATTERY_SWAP_TIME_MIN` | 3.0 |

**Impact:** Same as above — identical values, separate definitions.

**Fix:** Move to `config/settings.py`.

### 1.3 Battery Wh calculation (duplicated logic)

| File | Lines | Formula |
|---|---|---|
| `core/battery_model.py` | 64-65 | `battery_wh = mAh * voltage / 1000; usable = battery_wh * (1 - reserve/100)` |
| `core/resource_planner.py` | 90-95 | `battery_wh = mAh * voltage / 1000; usable = battery_wh * (1 - reserve/100)` |

**Impact:** The same mAh→Wh conversion is computed independently in two modules. `battery_model.py` (Phase 6) is the physics-correct version; `resource_planner.py` (v0.1) is the simpler legacy version. Both use the same formula and produce the same result.

**Fix:** Extract a helper `compute_battery_wh(mAh) -> (total_wh, usable_wh)` into `config/settings.py` (alongside `DroneSpec`) or into `core/battery_model.py` and import from there in `resource_planner`.

### 1.4 Liquid consumption calculation (duplicated logic)

| File | Lines | Formula |
|---|---|---|
| `core/liquid_model.py` | 59-61 | `total = area_ha * spray_rate; loads = ceil(total / tank); refills = loads - 1` |
| `core/resource_planner.py` | 101-104 | `liquid_needed = area_ha * spray_rate; loads = ceil(needed / capacity); refills = loads - 1` |

**Impact:** Identical algorithm in both modules. `resource_planner` is the v0.1 path; `liquid_model` is the Phase 6 path.

**Fix:** `resource_planner._compute_drone_resources()` should delegate liquid calculations to `liquid_model.estimate_liquid()` instead of reimplementing them.

### 1.5 Time formatting (similar but distinct)

| File | Function | Format |
|---|---|---|
| `core/mission_timeline.py:78` | `_format_time()` | `"{h}h {m:02d}m"` or `"{m}m {s:02d}s"` |
| `core/resource_planner.py:63-65` | inline | `"{h}h {m:02d}m"` |

**Impact:** Low risk — `resource_planner` uses a 2-line inline format. Not a functional duplicate but could be DRY-ed.

**Fix:** Optional — extract to a shared utility if desired, but no functional divergence risk.

---

## 2. Unused Imports

| File | Import | Issue |
|---|---|---|
| `utils/validators.py:6` | `typing.Optional` | Imported but never used |
| `ui/timeline_view.py:12` | `ui.swarm_view.DRONE_COLORS` | Imported but never used |
| `config/settings.py:8` | `dataclasses.field` | Imported but never used |
| `config/settings.py:9` | `typing.Optional` | Imported but never used |

**Fix:** Remove all four unused imports.

---

## 3. Dead Code / Unused Variables

| File | Line | Variable | Issue |
|---|---|---|---|
| `core/route_planner.py:73` | `total_time` | Assigned but never used (sum of all route times; only `max_time` is used) |
| `core/resource_planner.py:98` | `flights_per_battery` | Computed but never referenced (line 99's `battery_flights` is the one used in the return) |
| `core/swarm_planner.py:115` | `centroid` | Assigned but never used (in `_plan_strips`, centroid of strip_poly is computed but discarded) |

**Fix:** Remove all three dead assignments.

---

## 4. Duplicate Documentation

No duplicate documentation files detected. All doc files serve distinct purposes:
- `docs/roadmap/EEA Swarm Mission Planner_Roadmap_Ejecution.md` — master execution truth log
- `docs/roadmap/roadmap_v2_final_clean.md` — v0.2 design roadmap
- `docs/architecture/*.md` — distinct architecture documents (current, future v1, HAL)
- `docs/system_overview.md`, `docs/simulation_vs_reality.md` — non-overlapping

---

## 5. Geometry Centralization Verification

**Status: PASS — All geometry functions centralized in `core/geometry.py`**

| Function | Location | Consumers |
|---|---|---|
| `FieldGeometry.from_hectares()` | `core/geometry.py:33` | `mission_intake.py` |
| `FieldGeometry.from_points()` | `core/geometry.py:59` | `ui/mission_config.py` |
| `compute_polygon_orientation()` | `core/geometry.py:101` | `swarm_planner.py`, `route_planner.py` |
| `SectorGeometry` | `core/geometry.py:125` | Not consumed yet (available for Phase 7) |

No geometry logic exists outside `core/geometry.py`. Previous duplication of `compute_polygon_orientation()` (which existed in both `swarm_planner` and `route_planner`) was consolidated in Phase 5.

---

## 6. Physics Centralization Verification

**Status: PASS — All physics functions centralized in `core/drone_physics.py`**

| Function | Location | Consumers |
|---|---|---|
| `compute_effective_speed()` | `core/drone_physics.py:62` | `analyze_drone_physics()` |
| `compute_turn_penalty()` | `core/drone_physics.py:87` | `analyze_drone_physics()` |
| `compute_payload_power_factor()` | `core/drone_physics.py:107` | `battery_model.py` |
| `compute_wind_power_factor()` | `core/drone_physics.py:112` | `battery_model.py` |
| `compute_climb_time_s()` | `core/drone_physics.py:119` | Not consumed (available) |
| `compute_descend_time_s()` | `core/drone_physics.py:124` | Not consumed (available) |
| `analyze_drone_physics()` | `core/drone_physics.py:129` | `mission_timeline.py` |
| `PhysicsConfig` | `core/drone_physics.py:28` | `battery_model.py`, `mission_timeline.py` |

Note: `compute_climb_time_s()` and `compute_descend_time_s()` are not currently called. `mission_timeline.py` inlines the calculation (`altitude / climb_rate / 60`). This is a minor inconsistency but not a duplication — the timeline uses `physics_config.climb_rate_ms` directly.

---

## 7. Phase 7 Duplication Risk Check

**Question:** Will Phase 7 (Intelligence Layer) duplicate any existing planner logic?

**Finding:** No risk detected, given the following architecture:

| Phase 7 Component | Existing Module | Overlap? |
|---|---|---|
| Dynamic Drone Reallocation | `swarm_planner.py` | No — reallocation is a new event-driven capability; swarm_planner is a static partitioner |
| Swarm Optimization | `decision_engine.py` | No — optimization is multi-objective search; decision_engine is a rule-based classifier |
| Mission Adaptation | `mission_timeline.py` | Potential — adaptation will need to re-generate timelines. Should use `generate_timeline()` as the recomputation engine, not duplicate it |
| Swarm State Manager | None | New module — no existing state management |

**Recommendation for Phase 7:** The state manager and adaptation engine should consume the existing `generate_timeline()` and `plan_swarm()` functions, not duplicate their logic.

---

## 8. Summary of Issues Found

| # | Category | Severity | File(s) | Action |
|---|---|---|---|---|
| 1 | Duplicate constant | Medium | `liquid_model.py`, `resource_planner.py` | Consolidate `REFILL_TIME_MIN` to config |
| 2 | Duplicate constant | Medium | `battery_model.py`, `resource_planner.py` | Consolidate `BATTERY_SWAP_TIME_MIN` to config |
| 3 | Duplicate logic | Medium | `battery_model.py`, `resource_planner.py` | Extract battery Wh helper |
| 4 | Duplicate logic | Medium | `liquid_model.py`, `resource_planner.py` | Delegate liquid calc to `liquid_model` |
| 5 | Unused import | Low | `validators.py` | Remove `Optional` |
| 6 | Unused import | Low | `timeline_view.py` | Remove `DRONE_COLORS` |
| 7 | Unused import | Low | `config/settings.py` | Remove `field`, `Optional` |
| 8 | Dead variable | Low | `route_planner.py:73` | Remove `total_time` |
| 9 | Dead variable | Low | `resource_planner.py:98` | Remove `flights_per_battery` |
| 10 | Dead variable | Low | `swarm_planner.py:115` | Remove `centroid` |

**Total: 4 medium issues (duplicated logic/constants), 6 low issues (unused imports/dead code)**

---

## 9. Refactoring Plan

1. Add `REFILL_TIME_MIN` and `BATTERY_SWAP_TIME_MIN` to `config/settings.py`
2. Remove duplicate constants from `liquid_model.py`, `battery_model.py`, `resource_planner.py`
3. Add `compute_battery_wh()` helper to `core/battery_model.py`, use from `resource_planner.py`
4. Delegate liquid calculation in `resource_planner.py` to `liquid_model.estimate_liquid()`
5. Remove 4 unused imports and 3 dead variables
6. Run full regression suite — confirm 44/44 tests PASS with no behavioral changes
