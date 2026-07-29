# ORION Phase 10D.3 — Field Acquisition & Preparation — Implementation Report

## Objective

Transform the static planning experience into a real **field preparation
workflow**: create a field, upload imagery, annotate boundary / zones /
exclusion areas / obstacles, edit or remove geometry, and save/reload the field
definition — all as design-time data feeding the Phase 10D.2 Mission Definition
contract.

This phase enriches the Mission Definition contract established in 10D.2. It does
**not** introduce planning, routing, optimization, allocation, perception, or any
runtime behavior.

## Architecture position

```
Field Acquisition (UI)  →  FieldDefinition (contract)  →  MissionDefinition  →  Planning Core  →  Mission Package  →  Digital Twin
   this phase                extended in this phase
```

The UI only **collects and submits** structured field data. It never plans and
never talks to Hive / HAL / PX4 / MAVLink / ROS2 / Simulation / the Digital Twin
runtime. All field data flows through the existing design-time pipeline REST
surface.

## Contract extension (backend + TypeScript, kept in sync)

`FieldSpec` (embedded in a MissionDefinition) gains, all optional / defaulted so
existing 10D.2 payloads keep parsing unchanged:

| Field | Type | Purpose |
|-------|------|---------|
| `images` | `list[FieldImage]` | uploaded imagery references (metadata only) |
| `meters_per_pixel` | `float` (default `0.5`) | scale relating the annotation image to metric space |
| `location` | `str` | operator-entered site label |
| `notes` | `str` | free-text notes |

New `FieldImage`: `image_id`, `filename`, `source` (`satellite`/`drone`/`manual`),
`url`, `width_px`, `height_px`, `uploaded_ms`.

New standalone, persisted, reusable `FieldDefinition` = a `FieldSpec` plus `id`,
`version`, `created_ms`, `updated_ms`. This is what `/api/fields` stores and
returns; a MissionDefinition later references the same field data.

Geometry stays in **local metric meters** (`boundary_points`, `zones`,
`obstacles`) exactly as 10D.2 expects, so `FieldGeometry.from_points` and the
Planning Core consume drawn fields with zero changes. Operator drawings happen
in image-pixel space in the UI and are converted to meters on save using
`meters_per_pixel` — the UI performs a coordinate transform only, never planning.

## Backend

- `backend/mission_pipeline/models.py` — `FieldImage`, extended `FieldSpec`,
  new `FieldDefinition` (typed `to_json`/`from_json`); field (de)serialization
  updated for images + metadata.
- `backend/mission_pipeline/field_images.py` (new) — `FieldImageStore`
  abstraction + `LocalFieldImageStore` (filesystem, `data/field_images/`,
  git-ignored). Probes dimensions with Pillow, guards against path traversal,
  and is replaceable with object storage in Phase 11 behind the same interface.
- `backend/mission_pipeline/api.py` — field CRUD now validated through the typed
  `FieldDefinition`; new endpoints:
  - `POST /api/fields/{id}/images` — raw-body upload (no `python-multipart`
    dependency added); validates non-empty + max 25 MB; attaches the image
    reference to the stored field.
  - `GET /api/fields/{id}/images/{image_id}` — serves the stored bytes
    (read-only).
- `backend/twin_server.py` — constructs a default `LocalFieldImageStore`
  (`ORION_FIELD_IMAGE_DIR`, default `data/field_images`) and injects it into the
  pipeline router; `create_app` accepts an `image_store` override for tests.

## Frontend

- `src/contracts/mission.ts` — `FieldImage`, `FieldImageSource`, extended
  `FieldSpec`, `FieldDefinition`; new image endpoints in `PIPELINE_ENDPOINTS`.
- `src/lib/pipelineClient.ts` (new) — design-time REST client for the pipeline
  (fields CRUD, image upload, fleet inventory), separate from the Digital Twin
  runtime client. Resolves relative image URLs against the API base.
- `src/lib/fieldGeometry.ts` (new) — pure pixel↔metric transforms, shoelace area
  (m²/ha), and SVG path helpers. No planning.
- `src/components/fields/FieldCanvas.tsx` (new) — SVG annotation surface over the
  uploaded image: renders boundary/zones/obstacles + in-progress draft, converts
  clicks to image coordinates, supports selection in Select mode.
- `src/app/fields/page.tsx` (new) — field list + create form + delete.
- `src/app/fields/[fieldId]/page.tsx` (new) — preparation workspace: image
  upload (satellite/drone/manual) + image switcher, metadata form
  (name/crop/location/notes/scale), drawing tools (boundary, crop / management /
  treatment / exclusion zones, obstacles with kind), draft undo/finish/cancel,
  geometry list with rename / enable-toggle / remove, and save/reload.
- `src/components/layout/Sidebar.tsx` — added a **Fields** nav entry.

## Boundaries preserved

- Pipeline package imports only `core/`, `config`, `backend.serializers`, Pillow,
  and FastAPI — no Hive/HAL/PX4/MAVLink/ROS2/Simulation/Twin-runtime imports
  (scan clean).
- No planning, routing, optimization, scheduling, allocation, or perception in
  UI or the new backend code.
- Design-time endpoints never mutate Digital Twin runtime state (asserted by
  tests).
- Existing Mission Control workflow untouched.

## Known limitations (demonstration stage)

- `meters_per_pixel` is operator-provided (no georeferencing / GPS corner
  registration yet — that is 10D.6 scope). Area is computed from the drawn
  boundary and this scale.
- Images are stored on the local filesystem for the demo; commercial object
  storage swaps in behind `FieldImageStore`.
- No automatic perception / field detection — annotation is fully manual by
  design for this phase.
- No auth on uploads (Phase 11).
