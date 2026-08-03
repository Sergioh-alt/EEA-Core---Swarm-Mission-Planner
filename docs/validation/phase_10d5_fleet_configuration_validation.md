# Phase 10D.5 — Fleet Configuration: Validation Report

All commands run from the repository root (backend) and `orion-ui/` (frontend).
No CI is configured on this repository; validation is run locally.

## Summary

| Check | Command | Result |
|-------|---------|--------|
| Python regression | `python -m pytest -q` | **896 passed** |
| Fleet config tests | `python -m pytest tests/test_fleet_configuration.py -q` | **6 passed** |
| Validation-consistency test | `pytest tests/test_mission_designer.py -q` | passed |
| TypeScript | `npx tsc --noEmit` | clean (exit 0) |
| ESLint | `npx next lint` | no warnings or errors |
| Production build | `npx next build` | **18/18 routes** |
| Forbidden-import scan | grep on `backend/mission_pipeline/` | **0 hits** |

## Boundary / architecture verification

- `backend/mission_pipeline/` imports only `core/`, `config`, `utils.validators`,
  `backend.serializers`, FastAPI, PIL and stdlib. No `hive`, `hal`, `px4`,
  `mavlink`, `ros2`, `simulation`, `digital_twin`, or `twin_runtime` imports.
- `test_fleet_configuration_does_not_touch_runtime_state` asserts `GET
  /api/twin/state` is unchanged across mission creation + `POST
  /api/planning/compute`.
- The frontend workspace (`/missions/[missionId]/fleet`) uses only the
  design-time REST client (`pipelineClient`) — never the runtime WebSocket
  client. Fleet Summary is sums/min of static catalog specs plus an
  interface-completeness check; no consumption/feasibility is computed in the UI.

## Persistence verification

- `test_configured_fleet_roundtrip_preserves_all_fields` — enriched fleet
  (equipment, sensors, camera/sprayer/spreader, per-tank product assignment)
  survives `to_json`/`from_json`.
- `test_configured_fleet_persists_via_rest` — the configuration survives
  `POST /api/missions` → `GET /api/missions/{id}`.
- `test_legacy_fleet_without_config_still_parses` — 10D.4-era fleet items
  (no new fields) deserialize with safe defaults (backward compatibility).

## Precondition fix verification (Definition-valid semantics)

- `test_unknown_crop_is_non_blocking_warning_not_invalid` — an unknown crop
  (`grapes`) yields `validation.valid == True` with a warning present while
  `recommendation.feasible == True` — no contradiction.
- Blocking inputs (non-positive field size, zero drones, impossible wind,
  out-of-range temperature) remain errors → `valid == False` (unchanged).

## Browser E2E

See `phase_10d5_fleet_configuration_browser_report.md` for the recorded
end-to-end walkthrough (select heterogeneous fleet → configure equipment/tanks
→ assign products → review Fleet Summary → save → reload).
