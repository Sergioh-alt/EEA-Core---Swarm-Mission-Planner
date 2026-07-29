# ORIÓN Frontend — Functional Audit (UI Inventory)

**Type:** Product / UI inventory (not a code review, not an architecture review)
**Scope:** `orion-ui/` (Next.js 14 App Router GCS)
**Purpose:** Document the *current* user experience so the next development
stages (including Mission Planning) can be planned correctly.
**Method:** Static inspection of the frontend source at the current `main`.
**Constraints honored:** No code modified, no redesign, no new functionality —
documentation only.

---

## 0. How to read this document

Every interactive element is tagged with a **data source** and a **write
classification**:

| Tag | Meaning |
|-----|---------|
| **Twin/WS** | Value streamed from the Digital Twin over the WebSocket (`/ws/twin`) |
| **Twin/REST** | Value fetched on demand from the Digital Twin REST API |
| **Local UI** | Pure client-side UI state (Zustand / `useState`), no backend call |
| **Placeholder** | Static / mock content; not wired to any backend |
| **Intent** | Submits an operator intent (`POST /api/intents`) — the only write path |
| **Read-only** | Never mutates backend state |

**Runtime modes.** The UI has two modes, decided by `NEXT_PUBLIC_TWIN_API_URL`
(`src/lib/config.ts`):

- **LIVE mode** (env var set): all data comes from the Digital Twin API server
  (REST + WebSocket). The mock provider never runs.
- **Dev-fallback mode** (env var unset): a client-side mock provider
  (`src/lib/mockDataProvider.ts`) supplies state so a fresh clone still renders.
  No backend is contacted.

Both modes flow through the exact same Zustand stores and components, so the UI
is identical in layout; only the data origin differs.

---

## 1. Application shell & global chrome

Defined in `src/app/layout.tsx` → `ConnectionProvider` → `RootShell`
(`Sidebar` + `TopBar` + `<main>`).

### 1.1 Left Sidebar (`components/layout/Sidebar.tsx`)

Persistent, fixed-width (224px) vertical navigation on every page.

| Element | Location | Function | Behavior | Source | Write |
|---------|----------|----------|----------|--------|-------|
| ORION logo/wordmark | Top | Brand | Static | Placeholder | Read-only |
| Nav links (11) | Body | Route navigation | Client-side routing; active route highlighted via `usePathname` | Local UI | Read-only |
| Footer `ORION GCS v10C.5` | Bottom | Version label | Static | Placeholder | Read-only |

Nav items (in order): **Dashboard `/`, Control `/control`, Fleet `/fleet`,
Mission `/mission`, Map `/map`, Planning `/planning`, Deployment `/deployment`,
Replay `/mission/replay`, Analytics `/analytics`, Alerts `/alerts`, Settings
`/settings`.**

### 1.2 Top Bar (`components/layout/TopBar.tsx`)

Persistent 48px header on every page.

| Element | Function | Behavior | Source | Write |
|---------|----------|----------|--------|-------|
| Mission status badge | Current mission state | Shows only when swarm state present | Twin/WS | Read-only |
| `active/total active` count | Fleet size | Live counter | Twin/WS | Read-only |
| Connection badge | Transport health | Status dot + label + latency; **Reconnect** button in LIVE mode when Disconnected/Error | Twin/WS + Local UI | Read-only (Reconnect re-opens socket) |
| Alerts bell + unread badge | Jump to `/alerts` | Link; red count bubble | Twin/WS | Read-only |
| Active-failures counter | Failure count | Shows only when `active_failures > 0` | Twin/WS | Read-only |

### 1.3 App-Router status screens

Global recovery/UX states (no route of their own):

- `app/loading.tsx` — spinner during route transitions.
- `app/error.tsx` — route-level error boundary with **Try again**.
- `app/global-error.tsx` — root error boundary with **Reload**.
- `app/not-found.tsx` — dark 404 with link back to `/control`.

---

## 2. Page-by-page inventory

There are **12 routes** (11 nav entries + the dynamic drone-detail route).

### 2.1 Dashboard — `/` (`app/page.tsx`)

**Purpose:** Swarm mission overview / landing page.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| "Waiting for Digital Twin connection…" | Empty state | Shown until first swarm state arrives | Twin/WS | Read-only |
| Active Drones `x/y` | Metric card | Active vs. total | Twin/WS | Read-only |
| Global Health | Metric card | Swarm health + status dot | Twin/WS | Read-only |
| Active Failures | Metric card | `active_failures.length` | Twin/WS | Read-only |
| Unread Alerts | Metric card | From alert store | Twin/WS | Read-only |
| **Open Mission Control** | Button/link | Navigate to `/control` | Local UI | Read-only |
| Fleet Summary | Card | Per-drone health dot + battery % list | Twin/WS | Read-only |
| Environment | Card | Wind speed/direction, condition | Twin/WS | Read-only |

### 2.2 Mission Control — `/control` (`app/control/page.tsx`)

**Purpose:** Primary operational GCS view. This is the real, fully-wired
operational screen. 3-column layout: Fleet (left) | Map + bottom panels (center)
| Telemetry (right). Composed of six mission-control components — see §3.

### 2.3 Fleet Overview — `/fleet` (`app/fleet/page.tsx`)

**Purpose:** Grid of all drones.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Drone cards (grid) | Cards | Health, battery, state per drone | Twin/WS | Read-only |
| Card click | Action | `selectDrone` + navigate to `/fleet/{id}` | Local UI | Read-only |
| "No drones connected" | Empty state | Shown when fleet empty | Twin/WS | Read-only |

### 2.4 Drone Detail — `/fleet/[droneId]` (`app/fleet/[droneId]/page.tsx`)

**Purpose:** Single-drone detail.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Status card | Card | Health, armed, mode, task, comms | Twin/WS | Read-only |
| Position & Motion card | Card | Lat/lng/alt/speed/heading | Twin/WS | Read-only |
| Systems card | Card | Battery indicator, GPS availability/accuracy | Twin/WS | Read-only |
| Back to Fleet | Link | Navigate to `/fleet` | Local UI | Read-only |
| **Telemetry Charts** | Panel | "will render here when connected to Digital Twin" | **Placeholder** | Read-only |
| Not-found state | Text | "Drone {id} not found. Waiting for data…" | Twin/WS | Read-only |

> **Gap:** the per-drone Telemetry Charts panel is an unfilled placeholder even
> though per-drone history exists in `droneStore.droneHistories` and is already
> charted on `/control`.

### 2.5 Mission — `/mission` (`app/mission/page.tsx`)

**Purpose:** Mission monitoring & control (secondary to `/control`).

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Mission status badge | Badge | Current state | Twin/WS | Read-only |
| Mission Progress bar | Progress | `missionStore.progress` | Twin/WS | Read-only |
| **Mission Map** | Panel | "Mission map view will render when connected." | **Placeholder** | Read-only |
| **Start Mission** | Button | Enabled/disabled by status **but has no `onClick`** | **Placeholder** | — (no-op) |
| **Pause** | Button | Same — no handler | **Placeholder** | — (no-op) |
| **Stop** | Button | Same — no handler | **Placeholder** | — (no-op) |
| Event Log | List | Mission events | Twin/WS | Read-only |

> **Gap (important):** `/mission` duplicates parts of `/control` but its Intent
> Controls are **non-functional** (buttons render enabled/disabled states yet
> submit no intent), and its map is a placeholder. Functional intent submission
> lives only in `/control` (`IntentBar`) and `/deployment`.

### 2.6 Map — `/map` (`app/map/page.tsx`)

**Purpose:** Full-screen geographic visualization. Renders the real `MapView`
(§4) in a 3/4-width panel plus a side list of drone markers + environment. See
§4 for the full map inventory.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| MapView | Map | Full operational map | Twin/WS + Twin/REST | Read-only |
| Drone Markers list | List | Per-drone health dot + altitude | Twin/WS | Read-only |
| Environment | Card | Wind + condition | Twin/WS | Read-only |

### 2.7 Planning — `/planning` (`app/planning/page.tsx`)

**Purpose:** Read-only reference view of the planned mission profile.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| "Preview" badge | Badge | Marks page non-interactive | Placeholder | Read-only |
| **Planning Map** | Panel | "Interactive planning not enabled" | **Placeholder** | Read-only |
| Mission Parameters | Read-only fields | Mission Type=Survey, Altitude=50, Speed=5.0 (hard-coded) | **Placeholder** | Read-only |
| Waypoints | Text | Explains waypoints are backend-owned | Placeholder | Read-only |

> **Gap:** Planning is entirely static. There is no field loading, polygon
> drawing, waypoint editing, or mission creation. Values are hard-coded literals.

### 2.8 Deployment — `/deployment` (`app/deployment/page.tsx`)

**Purpose:** Pre-flight checklist + deploy.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Pre-flight checklist (6 checks) | List | Twin connected, drones detected, all healthy, GPS all, comms all, battery >80% all | Twin/WS (derived) | Read-only |
| **Deploy Mission** | Button | `submitIntent(START_MISSION)`; disabled when no state / no drones / running / pending | Twin/REST | **Intent** |
| Fleet Status grid | Cards | Battery + armed per drone | Twin/WS | Read-only |

### 2.9 Replay — `/mission/replay` (`app/mission/replay/page.tsx`)

**Purpose:** Historical mission reconstruction (read-only). See §5.

### 2.10 Analytics — `/analytics` (`app/analytics/page.tsx`)

**Purpose:** Mission & fleet performance analytics.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Dev-mode banner | Banner | Shown only in dev-fallback mode | Local UI | Read-only |
| Stat tiles (4) | Stats | Snapshots, progress, status, duration | Twin/REST (poll 3s) | Read-only |
| Battery Trends | Line chart | Per-drone battery over recorded steps | Twin/REST | Read-only |
| Fleet Utilization | Area chart | Active/failed over time | Twin/REST | Read-only |
| Alert Frequency | Bar chart | Counts by severity | Twin/REST | Read-only |
| Mission Summary | Panel | Coverage progress + status + duration | Twin/REST | Read-only |
| Empty-chart states | Placeholders | Per-chart "no data yet" messages | Twin/REST | Read-only |

> **Note:** Analytics is the one screen that **polls** (`/api/twin/analytics`
> every 3s via `useAnalytics`); all other live panels are event-driven over WS.

### 2.11 Alerts — `/alerts` (`app/alerts/page.tsx`)

**Purpose:** Full alert log.

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Severity filter tabs (All/Critical/Warning/Info) | Toggle buttons | Filter list | Local UI | Read-only |
| Active-only toggle | Toggle button | Filter list | Local UI | Read-only |
| Mark all read | Button | Zero the unread counter | Local UI | Read-only |
| Alert rows | List | Message, severity badge, timestamp, source, category, resolved time | Twin/WS | Read-only |
| "No alerts" | Empty state | When filter yields nothing | Local UI | Read-only |

### 2.12 Settings — `/settings` (`app/settings/page.tsx`)

**Purpose:** System configuration & status (read-only display).

| Element | Type | Function | Source | Write |
|---------|------|----------|--------|-------|
| Connection card | Card | Status badge, latency, reconnect attempts | Twin/WS + Local UI | Read-only |
| Display card | Card | Theme=Dark, Update Rate=1 Hz, **Version=10C.2** | **Placeholder** | Read-only |
| Architecture Info card | Card | Data source / channels / write path / decision authority (static text) | Placeholder | Read-only |
| Map Configuration card | Card | Provider "pending configuration", zoom, clustering (static text) | **Placeholder** | Read-only |

> **Gaps:** Settings has **no editable controls** (theme/update-rate/map token
> are display-only). The Version field reads `10C.2` (stale — sidebar shows
> `v10C.5`). Map config says Mapbox "pending configuration".

---

## 3. Mission Control inventory (`/control`)

Composed of six components under `components/mission-control/`.

### 3.1 Fleet Panel (`FleetPanel.tsx`) — left column

| Element | Function | Source | Write |
|---------|----------|--------|-------|
| Header "Fleet Status" + active count | Fleet size | Twin/WS | Read-only |
| Drone cards | Health dot, comms icon, battery bar+%, heading, altitude, speed, GPS OK/LOST, mode | Twin/WS | Read-only |
| Card click | Toggle-select drone (click-to-focus map + filter telemetry) | Local UI | Read-only |
| "No drones connected" | Empty state | Twin/WS | Read-only |

### 3.2 Map (`MapView.tsx`) — center. See §4.

### 3.3 Telemetry Panel (`TelemetryPanel.tsx`) — right column

| Element | Function | Source | Write |
|---------|----------|--------|-------|
| Header (selected drone or "All drones") | Context | Local UI | Read-only |
| Battery chart | Recharts line, 0–100%, last 60 pts | Twin/WS (history) | Read-only |
| Altitude chart | Recharts line, 0–50m | Twin/WS (history) | Read-only |
| Speed chart | Recharts line, 0–8 m/s | Twin/WS (history) | Read-only |

Selection scoping: if a drone is selected, charts show only it; otherwise the
first 3 drones.

### 3.4 Mission Status Panel (`MissionStatusPanel.tsx`) — bottom-left

| Element | Function | Source | Write |
|---------|----------|--------|-------|
| Status badge | Mission state | Twin/WS | Read-only |
| Mission id + elapsed timer | Identity/duration | Twin/WS + Local UI clock | Read-only |
| Progress bar | Coverage %, color by state | Twin/WS | Read-only |
| `active/total drones` | Fleet size | Twin/WS | Read-only |
| Event Log (last 20, reversed) | Icon per type (START/PAUSE/RESUME/STOP/FAILURE/RECOVERY/MILESTONE) | Twin/WS | Read-only |

### 3.5 Alert Feed (`AlertFeed.tsx`) — bottom-center

| Element | Function | Source | Write |
|---------|----------|--------|-------|
| Header + unread bubble | Count | Twin/WS | Read-only |
| Mark read | Zero unread | Local UI | Read-only |
| Alert items (last 30) | Severity icon/color, message, timestamp, source, resolved flag | Twin/WS | Read-only |
| "No alerts" | Empty state | Twin/WS | Read-only |

### 3.6 Intent Bar (`IntentBar.tsx`) — bottom strip (**the operator control**)

| Button | Intent submitted | Disabled when | Source | Write |
|--------|------------------|---------------|--------|-------|
| **Start** | `START_MISSION` (or `RESUME_MISSION` if paused) | status = RUNNING | Twin/REST | **Intent** |
| **Pause** | `PAUSE_MISSION` | status ∈ {IDLE, PAUSED, COMPLETED, FAILED} | Twin/REST | **Intent** |
| **Stop** | `STOP_MISSION` | status ∈ {IDLE, COMPLETED, FAILED} | Twin/REST | **Intent** |
| **Replay** | (navigates to `/mission/replay`) | status = RUNNING | Local UI | Read-only |

All writes are intent submissions via `POST /api/intents`; the UI never mutates
Twin state directly. Rejections/unreachable are swallowed (surfaced only via the
connection badge).

---

## 4. Map inventory (`MapView.tsx`, used by `/control` and `/map`)

**Engine:** Mapbox GL JS. With `NEXT_PUBLIC_MAPBOX_TOKEN` → Mapbox `dark-v11`.
Without a token → **OpenStreetMap raster fallback** (a small "OSM tiles" note is
shown). Default center `38.7223, -9.1393`, zoom 15.

### 4.1 Layers (all toggled locally; never mutate backend)

| Layer | Default | Content | Source |
|-------|---------|---------|--------|
| Drones | on | Heading-rotated SVG markers colored by health, id label; recolor red if active alert | Twin/WS |
| Planned routes | on | Dashed per-drone lines | Twin/REST (`/api/mission/geometry`) or mock geometry |
| Executed routes | on | Solid cyan lines accumulated from live positions (last 500 pts/drone) | Twin/WS |
| Mission zones | on | Field polygon fill + dashed outline | Twin/REST geometry |
| Coverage | **off** | Wide translucent green swath under executed path | Twin/WS |
| Alerts | on | Drives red drone-marker emphasis | Twin/WS |
| Event markers | **off** | Waypoint circles | Twin/REST geometry |

### 4.2 Controls & interactions

| Element | Function | Source | Write |
|---------|----------|--------|-------|
| **Layers** button + panel | Eye/EyeOff toggles per layer | Local UI | Read-only |
| Drone marker click | `selectDrone` | Local UI | Read-only |
| Fly-to on selection | Animates to selected drone at zoom 17 | Local UI | Read-only |
| Mapbox pan/zoom/rotate | Default GL nav gestures | Local UI | Read-only |
| OSM-fallback note | Info chip when no token | Placeholder | Read-only |
| ResizeObserver | Keeps canvas sized to container | Local UI | Read-only |

### 4.3 Map capabilities NOT present

No drawing tools, no polygon/route editing, no measurement/ruler, no coordinate
readout under the cursor, no explicit zoom/compass/scale buttons, no geocoder/
search, no basemap switcher, no marker clustering (Settings text claims
"clustering enabled for 20+ drones" but `MapView` does not implement it).

---

## 5. Replay inventory (`/mission/replay`)

**Purpose:** Read-only reconstruction of recorded history from Digital-Twin
snapshots (`POST /api/twin/replay`).

| Element | Function | Source | Write |
|---------|----------|--------|-------|
| No-timeline empty state | **Load recorded timeline** button (LIVE only) | Twin/REST | Read-only |
| Empty-timeline state | "timeline is empty" + Back | Twin/REST | Read-only |
| Frame scatter (SVG) | Normalized drone positions for current frame, colored by health | Twin/REST | Read-only |
| Frame table | Per-drone battery/health/task | Twin/REST | Read-only |
| Timestamp + `frame x/N` + unload | Position readout / reset | Local UI | Read-only |
| Timeline scrubber (range) | Jump to any frame | Local UI | Read-only |
| First-frame / Last-frame | Skip to ends | Local UI | Read-only |
| Slower / Faster | Halve/double playback speed | Local UI | Read-only |
| Play / Pause | Auto-advance ~2 fps × speed | Local UI | Read-only |

**Supported:** play, pause, timeline scrub, jump-to-first/last, variable speed.
**Not present:** jump-to-exact-timestamp input (store has `jumpToTimestamp` but
no UI field binds to it), per-drone replay view (`/api/twin/replay/drone/{id}`
client method exists but is unused), map-based replay (replay uses the SVG
scatter, not `MapView`).

---

## 6. Navigation audit

- **Structure:** single flat sidebar (11 links), no sub-menus/accordions. The
  only nested route is `/mission/replay` (reached via the "Replay" sidebar link
  and the `/control` Intent Bar "Replay" button).
- **Active state:** exact match for `/`; prefix match otherwise (so `/fleet` and
  `/fleet/{id}` both highlight Fleet).
- **Transitions:** client-side App-Router navigation; `app/loading.tsx` spinner
  between routes.
- **Breadcrumbs:** none. Back navigation is ad-hoc ("Back to Fleet" link on
  drone detail; "Back"/"unload" on replay).
- **Quick actions / cross-links:** Dashboard → "Open Mission Control";
  TopBar bell → `/alerts`; Fleet card → drone detail; `/control` Intent Bar
  "Replay" → `/mission/replay`.
- **No** global search, command palette, user menu, or notifications drawer.

---

## 7. Current functional flow (open ORIÓN → finish a simulated mission)

**Supported today (LIVE mode, backend running):**

1. App loads → WebSocket connects → TopBar shows Connected + fleet count.
2. Dashboard shows swarm overview; operator opens **Mission Control** `/control`.
3. Fleet/telemetry/map/alerts stream live at ~1 Hz; field polygon + planned
   routes drawn from backend geometry.
4. Operator reviews **Deployment** pre-flight checklist.
5. Operator submits **START_MISSION** (Intent Bar or Deployment).
6. Mission transitions IDLE→RUNNING; drones move along the fixed backend
   coverage route; executed routes accumulate; progress advances.
7. Operator can **Pause / Resume / Stop** via intents; events append to the log.
8. Mission reaches COMPLETED; **Analytics** shows snapshots/progress/duration.
9. Operator opens **Replay**, loads the recorded timeline, scrubs/plays back.
10. On backend interruption the UI degrades gracefully and auto-reconnects
    (manual **Reconnect** available).

**Unsupported / missing pieces of a full demo workflow:**

- **Mission creation** — no UI to create/name a mission; the demo mission is
  implicit and backend-owned.
- **Field loading** — no way to load/import/select a field; the polygon is a
  fixed backend geometry (mock fallback when offline).
- **Mission planning** — `/planning` is a static preview; no field drawing,
  waypoint editing, altitude/speed configuration, or plan submission.
- **`/mission` intent buttons** — render but do nothing (no handlers).
- **Per-drone telemetry charts** on `/fleet/{id}` — placeholder.
- **Settings** — no editable settings; version label stale (`10C.2`).
- **Replay** — no timestamp-jump field, no per-drone replay, no map replay.

---

## 8. Gap analysis (existing vs. missing for a complete demonstration)

> Identification only — no implementation proposed (per task constraints).

### 8.1 Fully functional today
- Live Mission Control (`/control`): map, fleet, telemetry, mission status,
  alerts, intent submission.
- Full operational **Map** with 7 toggleable layers + click-to-focus.
- **Deployment** pre-flight + START intent.
- **Analytics** from backend snapshots.
- **Replay** load / scrub / play / speed / first-last.
- **Alerts** log with filters.
- Robust transport: reconnect, retry, error/loading/not-found boundaries.

### 8.2 Placeholder / non-functional (exists visually, not wired)
- `/mission` Intent Controls (no `onClick`) and Mission Map placeholder.
- `/fleet/{id}` Telemetry Charts placeholder.
- `/planning` entire screen (static preview; hard-coded parameters).
- `/settings` Display/Architecture/Map cards (display-only; stale version).

### 8.3 Absent capabilities (no UI at all)
- Mission creation / naming / lifecycle authoring.
- Field loading / import / selection.
- Interactive planning: polygon drawing, waypoint CRUD, route/altitude/speed
  editing, plan preview & submission.
- Map drawing/measurement tools, cursor coordinate readout, basemap switch,
  marker clustering (claimed in Settings text but not implemented).
- Replay: jump-to-timestamp input, per-drone replay timeline, map-based replay.
- Multi-mission / mission history browsing (analytics references a single
  current mission only).
- Editable settings (theme, update rate, Mapbox token entry).
- Auth / operator identity (intents hard-code `user_id: "operator"`).

### 8.4 Consistency notes (observations, not defects to fix here)
- Two overlapping "mission" surfaces: `/control` (functional) and `/mission`
  (partly placeholder) — a future stage should clarify their relationship.
- Settings version (`10C.2`) lags the sidebar (`v10C.5`).
- Unused-but-available client capabilities: `getDroneReplay`, `listSnapshots`,
  `getSnapshot`, `getDroneState`, `replayStore.jumpToTimestamp` — wired methods
  with no UI binding yet.

---

## 9. Route → data-source summary

| Route | Primary source | Writes? |
|-------|----------------|---------|
| `/` Dashboard | Twin/WS | none |
| `/control` Mission Control | Twin/WS + Twin/REST | Intent (Start/Pause/Stop) |
| `/fleet` | Twin/WS | none |
| `/fleet/{id}` | Twin/WS | none (charts placeholder) |
| `/mission` | Twin/WS | none (buttons inert) |
| `/map` | Twin/WS + Twin/REST | none |
| `/planning` | Placeholder | none |
| `/deployment` | Twin/WS + Twin/REST | Intent (START_MISSION) |
| `/mission/replay` | Twin/REST | none (read-only) |
| `/analytics` | Twin/REST (poll 3s) | none |
| `/alerts` | Twin/WS | none |
| `/settings` | Twin/WS + Placeholder | none |

**Architecture position (observed):** the frontend is a visualization +
intent-submission layer. Every write is a `POST /api/intents`. All reads are
Digital-Twin REST/WebSocket. No component contacts PX4/MAVLink/ROS2/Hive/HAL
directly, and no planning/scheduling/optimization/allocation logic exists in the
UI — consistent with the documented boundary.
