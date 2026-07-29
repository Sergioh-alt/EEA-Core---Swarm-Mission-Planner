# ORION Phase 10D.3 — Field Acquisition & Preparation — Validation Report

Scope validated: field creation workflow, image upload/reference, field
metadata + geometry persistence and reload, Mission Definition contract
compatibility, regression, boundaries, and builds.

## Summary

| Check | Result |
|-------|--------|
| Phase 10D.3 backend tests (`test_field_acquisition.py`) | **10 passed** |
| Mission Definition pipeline tests (`test_mission_pipeline.py`) | 14 passed |
| Full Python regression (`pytest -q`) | **882 passed** |
| TypeScript (`tsc --noEmit`) | clean |
| ESLint (`next lint`) | 0 warnings/errors |
| Next.js production build (`next build`) | **16/16 routes** |
| Forbidden-import / boundary scan (pipeline package) | 0 matches |
| Runtime-state isolation (design-time endpoints) | asserted by tests |

## Backend / contract validation

`test_field_acquisition.py` (10 tests):

- `FieldDefinition` roundtrip preserves images + metadata + geometry.
- Backward compatibility: a minimal 10D.2-style field (no images/metadata)
  still parses with safe defaults (`meters_per_pixel=0.5`, empty images).
- `LocalFieldImageStore` saves + serves bytes, probes dimensions (Pillow), and
  rejects path traversal.
- A `FieldSpec` carrying images/metadata builds a Mission Package unchanged
  (area 12.0 ha from the drawn boundary; `is_synthetic=False`) — proving the
  extension does not disturb Planning-Core geometry.
- Field CRUD with metadata via REST (create → version 1, update → version 2).
- Image upload attaches a reference to the stored field and the bytes are
  retrievable as `image/png` with correct dimensions.
- Upload validation: empty body → 400, upload to a missing field → 404.
- End-to-end create → annotate (PUT) → reload preserves boundary, zones (kind
  `exclusion`), and obstacles.
- Field + image endpoints do not change Digital Twin `mission_status`.

## Persistence validation

- Field records persist through the replaceable `DefinitionStore` (SQLite
  default `data/mission_pipeline.db`, git-ignored) as typed `FieldDefinition`
  JSON — no second/parallel persistence system introduced.
- Uploaded image bytes persist under `data/field_images/{field_id}/` via the
  replaceable `FieldImageStore` (git-ignored); references live in the field
  record. Reload restores geometry, metadata, and image references.

## Mission Definition compatibility

- `FieldSpec` extension is additive and defaulted; existing MissionDefinition
  payloads and all 14 pipeline tests pass unchanged.
- Drawn geometry remains local metric meters, consumed directly by
  `FieldGeometry.from_points` and the Planning Core.

## Boundary validation

- `backend/mission_pipeline/` imports only `core/`, `config`,
  `backend.serializers`, Pillow, FastAPI — scan for
  hive/hal/px4/mavlink/ros2/simulation/digital_twin/twin_runtime/planner/
  optimizer imports returns **0 matches**.
- UI field workflow talks only to the design-time pipeline REST surface
  (`/api/fields*`, `/api/fleet/inventory`). No planning/routing/optimization/
  allocation in the UI; drawing performs coordinate transforms only.

## Build validation

- `tsc --noEmit`: clean.
- `next lint`: no warnings or errors.
- `next build`: 16/16 routes, including `/fields` (static) and
  `/fields/[fieldId]` (dynamic).

## Browser workflow validation

Performed against the live backend (`NEXT_PUBLIC_TWIN_API_URL` set) — see the
recording attached to the PR. Verified: create field → open preparation
workspace → upload image → draw boundary → add crop/exclusion zones → mark
obstacle → rename/remove geometry → Save → Reload restores the saved definition.

## Known limitations

Operator-provided scale (no georeferencing yet — 10D.6); local-filesystem image
storage for the demo (replaceable); manual annotation only (no perception); no
upload auth (Phase 11).
