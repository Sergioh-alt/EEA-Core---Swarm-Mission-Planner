# Phase 10C.1 — Navigation Map

**Status:** DESIGN SPECIFICATION  

---

## 1. Navigation Hierarchy

```
ORION GCS
  |
  +-- Dashboard (/)
  |     Primary operator view. Swarm summary, mission status,
  |     alerts feed, environment, mini map.
  |
  +-- Fleet (/fleet)
  |     |   Grid of all drones with live status cards.
  |     |   Battery distribution chart.
  |     |
  |     +-- Drone Detail (/fleet/[droneId])
  |           Full telemetry: position map, battery, velocity,
  |           GPS, communication, health, telemetry history charts.
  |
  +-- Mission (/mission)
  |     |   Active mission: timeline bar, task list, event log,
  |     |   coverage progress chart.
  |     |
  |     +-- Replay (/mission/replay)
  |           Snapshot-based replay: controls (play/pause/scrub/speed),
  |           frame timeline, snapshot list, state comparison.
  |
  +-- Field Map (/map)
  |     Full-screen Mapbox GL: farm polygon, sectors, drone markers,
  |     flight paths, wind indicator, failure overlays.
  |     Toggle layers: Drones, Paths, Zones, Wind.
  |
  +-- Alerts (/alerts)
  |     Alert center: filter by severity, type.
  |     Historical alert list, severity distribution chart.
  |
  +-- Settings (/settings)
        Display preferences, alert thresholds (display-only),
        connection status.
```

---

## 2. Route Table

| Route | Page Component | Layout | Data Source | Update Mode |
|-------|---------------|--------|------------|-------------|
| `/` | DashboardPage | Shell + Sidebar | SwarmState (full) | WebSocket 1 Hz |
| `/fleet` | FleetPage | Shell + Sidebar | DroneState[] | WebSocket 1 Hz |
| `/fleet/[id]` | DroneDetailPage | Shell + Sidebar | DroneState + history | WebSocket 2 Hz |
| `/mission` | MissionPage | Shell + Sidebar | SwarmState.mission + events | WebSocket 1 Hz |
| `/mission/replay` | ReplayPage | Shell + Sidebar | Snapshots + ReplayTimeline | On-demand REST |
| `/map` | MapPage | Shell + Sidebar (collapsed) | DroneState[] positions | WebSocket 2 Hz |
| `/alerts` | AlertsPage | Shell + Sidebar | Alert stream | WebSocket event-driven |
| `/settings` | SettingsPage | Shell + Sidebar | Local config | Static |

---

## 3. Navigation Interactions

### 3.1 Sidebar Behavior
- Always visible (collapsed icon-only on `/map` for maximum map area)
- Active route highlighted
- Alert badge count on Alerts item
- Connection status indicator at bottom

### 3.2 TopBar Behavior
- Always visible across all routes
- Shows: ORION logo, LIVE badge, current mission status, alert count, help
- LIVE badge: green when WebSocket connected, red when disconnected

### 3.3 Deep Linking
- `/fleet/1` links directly to Drone 1 detail
- `/mission/replay?version=42` links to specific snapshot frame
- All routes are bookmarkable and shareable

### 3.4 Cross-Navigation Shortcuts
- Click drone on Dashboard mini map → `/fleet/[id]`
- Click drone on Field Map → opens DroneDetailPanel overlay
- Click alert in AlertsFeed → `/alerts` with filter
- Click "View Replay" in Mission → `/mission/replay`

---

## 4. Page Transition Rules

| From | To | Trigger | Behavior |
|------|----|---------|----------|
| Dashboard | Fleet | Sidebar click | Full page transition |
| Dashboard | Drone Detail | Click drone card on mini map | Navigate to `/fleet/[id]` |
| Fleet | Drone Detail | Click drone card | Navigate to `/fleet/[id]` |
| Drone Detail | Fleet | Back button | Navigate to `/fleet` |
| Mission | Replay | "View Replay" button | Navigate to `/mission/replay` |
| Any page | Alerts | Click alert badge in TopBar | Navigate to `/alerts` |
| Map | Drone Detail | Click drone marker | Overlay panel (no navigation) |

---

## 5. Responsive Behavior

| Viewport | Sidebar | Layout | Map |
|----------|---------|--------|-----|
| Desktop (>1280px) | Full sidebar with labels | Multi-column grids | Full-size |
| Tablet (768-1280px) | Icon-only sidebar | 2-column grids | Reduced layers |
| Mobile (<768px) | Bottom nav bar | Single column, stacked | Touch-optimized |
