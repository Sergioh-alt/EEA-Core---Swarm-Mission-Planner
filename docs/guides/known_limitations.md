# ORIÓN Mission Control — Known Limitations

These are intentional scope boundaries and demonstration-environment characteristics
as of Phase 10C.5. None are defects; each is consistent with the fixed system
architecture (visualization + intent submission only; Digital Twin as SSOT).

## Demonstration mission geometry
- The mission follows a **fixed lawnmower coverage route** owned by the backend /
  Digital Twin. There is no live Planner/Optimizer in the loop for the demo; the UI
  never generates routes. This is by design for a reproducible demonstration.

## Analytics reflect real backend state
- Analytics visualize only backend snapshot-derived data (no invented calculations).
  When **no failures are injected**, battery trends are near-flat and the
  alert-frequency chart is empty. Injecting failures produces populated trends.

## Analytics polling
- `/analytics` polls `/api/twin/analytics` every 3 s. This endpoint is an on-demand
  backend aggregation, so polling is acceptable here; live operational panels use
  event-driven WebSocket updates rather than polling.

## Third-party Recharts warning
- The browser console shows: *"Support for defaultProps will be removed from
  function components in a future major release."* This originates from Recharts'
  `XAxis`/`YAxis` internals, not application code. It is functionally harmless and is
  **not** suppressed (a global `console.error` override could hide real errors).

## Map tiles
- Without `NEXT_PUBLIC_MAPBOX_TOKEN`, the map uses an OpenStreetMap raster fallback
  instead of Mapbox Dark styling. All markers, routes, zones, and layer toggles work
  in both modes.
- In the OSM fallback, `mapbox-gl` still fires its usage-telemetry requests
  (`events.mapbox.com`, `api.mapbox.com/map-sessions`) using the placeholder token,
  so the browser console shows **CORS / `ERR_FAILED`** entries for those third-party
  calls. They are harmless (map rendering is unaffected) and disappear once a real
  `NEXT_PUBLIC_MAPBOX_TOKEN` is supplied. They are not application errors and are not
  suppressed. Similarly, briefly interrupting the backend (e.g. the reconnect drill)
  logs transient `WebSocket connection ... failed` entries until auto-reconnect
  succeeds; these clear on reconnection.

## Runtime payload validation
- REST/WebSocket payloads are typed to the Digital Twin contract and parsed
  defensively (timeouts, malformed-JSON handling, bounded reconnect/dedup), but the
  clients do not perform full runtime schema validation of every field. The backend
  is the trusted, contract-tested source.

## Scale
- The demonstration runs 3 drones. The architecture and rendering were designed with
  larger fleets in mind (see `docs/architecture/ui/phase_10c1_scalability_strategy.md`),
  but 200+ drone scale has not been load-tested in this phase.
