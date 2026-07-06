# Phase 10C.1 — Scalability Strategy

**Status:** DESIGN SPECIFICATION  

---

## 1. Scaling Dimensions

The UI must scale across three independent dimensions without architectural changes:

| Dimension | Current | Near-term | Long-term |
|-----------|---------|-----------|-----------|
| Drone count | 3 | 20-50 | 100+ |
| Concurrent missions | 1 | 2-5 | 10+ |
| Data volume (state updates/sec) | 3/s | 50/s | 200+/s |
| Snapshot history | ~100 | ~10,000 | 100,000+ |
| Concurrent operators | 1 | 3-5 | 10+ |

---

## 2. Drone Count Scaling

### 2.1 UI Adaptation by Fleet Size

| Fleet Size | Fleet View | Map View | Dashboard |
|-----------|-----------|---------|-----------|
| 1-5 | Large cards with full detail | Individual markers with labels | All drones visible |
| 6-20 | Medium cards in grid | Individual markers, labels on hover | Summary metrics |
| 21-50 | Compact cards with key metrics | Markers without labels, cluster nearby | Aggregated view |
| 51-100 | Table view with sorting/filtering | Cluster markers by proximity | Statistical summary |
| 100+ | Paginated table, search, filters | Heatmap + cluster markers | Aggregated KPIs only |

### 2.2 Rendering Strategy

```
Fleet rendering decision tree:

  droneCount <= 20?
    → Render individual DroneCard components
    → Each card subscribes to its own drone state
    → Full detail visible without interaction

  droneCount <= 50?
    → Render compact DroneCard (status dot + battery bar)
    → Detail on click/hover
    → Virtualized list (only visible cards in DOM)

  droneCount > 50?
    → Switch to table view
    → Virtual scrolling (react-window)
    → Only render visible rows
    → Client-side filtering and sorting
```

### 2.3 Map Marker Scaling

```
Map marker strategy:

  droneCount <= 20:
    → Individual markers with heading arrow
    → Label always visible (drone ID)
    → Flight path trails (last 30 seconds)

  droneCount <= 50:
    → Individual markers, no labels (show on hover)
    → Flight paths disabled by default (toggle)
    → Cluster markers when zoom < threshold

  droneCount > 50:
    → Cluster markers at low zoom
    → Expand clusters on zoom in
    → No flight paths (too many overlaps)
    → Heatmap layer option for density visualization

  droneCount > 200:
    → Heatmap only at low zoom
    → Individual markers only at high zoom
    → Server-side viewport filtering
```

---

## 3. Mission Scaling

### 3.1 Single Mission (Current)

```
Dashboard → shows active mission
Mission page → dedicated to one mission
Fleet → all drones belong to one mission
```

### 3.2 Multi-Mission (2-5)

```
Dashboard → mission selector dropdown + summary per mission
Mission page → tabbed interface, one tab per active mission
Fleet → drones grouped by mission assignment
Map → color-coded by mission (different hue per mission)
```

### 3.3 Multi-Mission (5+)

```
Dashboard → mission list with search/filter + aggregated KPIs
Mission page → searchable mission list → drill into detail
Fleet → filterable by mission, assignment column in table
Map → mission filter control, toggle mission layers
```

### 3.4 Mission History

| History Size | Strategy |
|-------------|----------|
| < 100 | Load all in client, local search |
| 100-1,000 | Paginated REST API, server search |
| 1,000+ | Server-side search with indexing, date range filters |

---

## 4. Data Volume Scaling

### 4.1 WebSocket Message Rate

| Strategy | Threshold | Action |
|----------|----------|--------|
| Full state push | <= 20 drones | Send complete SwarmState at 1 Hz |
| Delta updates | 20-50 drones | Send only changed DroneState fields |
| Viewport filtering | 50+ drones | Server only sends drones visible on map |
| Batched deltas | 100+ drones | Batch delta updates, send at 0.5 Hz |
| Tiered updates | 200+ drones | Selected drone at 2 Hz, visible at 1 Hz, rest at 0.2 Hz |

### 4.2 Client-Side Data Management

```
Data retention strategy:

  Drone history buffer:
    → Keep last 300 data points per drone (5 min at 1 Hz)
    → Ring buffer (oldest evicted automatically)
    → Persist to localStorage for session recovery

  Alert buffer:
    → Keep last 500 alerts in memory
    → Older alerts fetched on demand from REST
    → Auto-dismiss INFO alerts after 60 seconds

  Replay data:
    → Loaded on demand (not cached permanently)
    → Maximum 1000 frames in memory
    → Paginate for longer timelines
```

### 4.3 Chart Data Windowing

| Chart | Default Window | Max Window | Resolution |
|-------|---------------|------------|------------|
| Battery over time | Last 5 minutes | Last 1 hour | 1s per point |
| Altitude profile | Last 5 minutes | Last 1 hour | 1s per point |
| Speed chart | Last 5 minutes | Last 30 min | 1s per point |
| Coverage progress | Full mission | Full mission | 5s per point |
| Alert timeline | Last 1 hour | Last 24 hours | Event-driven |

When data exceeds the max window, downsample older data (average every N points).

---

## 5. Snapshot & Replay Scaling

### 5.1 Snapshot Storage

| Snapshot Count | UI Strategy |
|---------------|-------------|
| < 100 | Load full list, local filtering |
| 100-1,000 | Paginated list (50 per page), date range filter |
| 1,000-10,000 | Server-side pagination + search by version/date |
| 10,000+ | Summary view (one entry per minute), drill-in for detail |

### 5.2 Replay Performance

| Frame Count | Strategy |
|-------------|----------|
| < 100 | Load all frames at once, instant scrubbing |
| 100-500 | Load all frames, lazy render (only current + adjacent) |
| 500-2,000 | Load in chunks of 100, prefetch next chunk |
| 2,000+ | Stream frames from server, buffer window of 200 |

---

## 6. Concurrent Operator Scaling

### 6.1 Multi-Operator Architecture

```
Operator A (Dashboard)  ─┐
Operator B (Map)         ─┼── WebSocket Server ── Digital Twin
Operator C (Fleet)       ─┘        |
                                   ├── shared state stream
                                   ├── per-client subscriptions
                                   └── independent view state
```

### 6.2 Per-Operator State

| State Type | Scope | Shared? |
|-----------|-------|---------|
| SwarmState | Global | Yes (same data to all operators) |
| Selected drone | Per-operator | No |
| Alert filters | Per-operator | No |
| Map viewport | Per-operator | No |
| Replay position | Per-operator | No |
| Display settings | Per-operator | No |

### 6.3 WebSocket Fan-Out

| Operators | Strategy |
|-----------|----------|
| 1-5 | Direct push from Digital Twin to each client |
| 5-20 | WebSocket server with broadcast (shared serialization) |
| 20+ | Redis pub/sub for horizontal scaling + multiple WS servers |

---

## 7. Performance Budgets

### 7.1 Target Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| First Contentful Paint | < 1.5s | Lighthouse |
| Time to Interactive | < 3.0s | Lighthouse |
| State update latency | < 100ms | WebSocket → render |
| Map marker update | < 50ms | Position change → visual update |
| Chart render | < 200ms | Data update → chart redraw |
| Page transition | < 300ms | Click → new page rendered |
| Memory (20 drones) | < 100 MB | Browser DevTools |
| Memory (100 drones) | < 250 MB | Browser DevTools |

### 7.2 Bundle Size Budget

| Chunk | Max Size (gzip) |
|-------|----------------|
| Initial (layout + dashboard) | 150 KB |
| Map page (Mapbox GL) | 200 KB |
| Charts (Recharts) | 80 KB |
| Replay page | 50 KB |
| Total (all routes loaded) | 500 KB |

---

## 8. Future Extension Points

### 8.1 Planned Extensions (Phase 10C.2+)

| Extension | Architecture Impact | Scaling Concern |
|-----------|-------------------|----------------|
| 3D map view | New map renderer option | GPU memory for large fleets |
| Video feed overlay | New component, WebRTC | Bandwidth per drone camera |
| Weather API integration | New data source to EnvironmentCard | API rate limits |
| Multi-farm support | Farm selector in navigation | Data partitioning |
| Mobile app | React Native shared types | Reduced feature set for mobile |
| Historical analytics | New Analytics page | Large dataset queries |

### 8.2 Extension Guidelines

1. New pages: add route to App Router, register in Sidebar
2. New data sources: add to Zustand stores, never bypass Digital Twin
3. New visualizations: add to component hierarchy, use existing chart library
4. New alert types: extend Alert interface, add to AlertCard renderer
5. New drone types: handled by DroneState model (no UI changes needed)
