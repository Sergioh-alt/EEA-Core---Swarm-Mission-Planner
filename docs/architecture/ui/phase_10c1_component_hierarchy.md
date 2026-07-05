# Phase 10C.1 — Component Hierarchy

**Status:** DESIGN SPECIFICATION  

---

## 1. Component Tree

```
<RootLayout>
  <ConnectionProvider>          # WebSocket connection context
    <StoreProvider>             # Zustand store initialization
      <TopBar>
        <Logo />
        <LiveBadge />           # WebSocket status
        <MissionStatusBadge />  # Current mission state
        <AlertBadge />          # Unread alert count
        <HelpButton />
      </TopBar>

      <Sidebar>
        <NavItem icon="dashboard" route="/" />
        <NavItem icon="fleet" route="/fleet" />
        <NavItem icon="mission" route="/mission" />
        <NavItem icon="map" route="/map" />
        <NavItem icon="alerts" route="/alerts" badge={alertCount} />
        <NavItem icon="settings" route="/settings" />
        <ConnectionIndicator />
      </Sidebar>

      <PageShell>
        {children}              # Route-specific page content
      </PageShell>
    </StoreProvider>
  </ConnectionProvider>
</RootLayout>
```

---

## 2. Page Components

### 2.1 DashboardPage (/)

```
<DashboardPage>
  <Grid cols={2}>
    <SwarmSummaryCard>
      <MetricCard label="Total" value={totalDrones} />
      <MetricCard label="Active" value={activeDrones} />
      <MetricCard label="Failed" value={failedDrones} />
      <SystemHealthBadge health={globalHealth} />
    </SwarmSummaryCard>

    <MissionStatusCard>
      <StatusDot status={missionStatus} />
      <MetricCard label="Mission" value={missionId} />
      <MetricCard label="Status" value={missionStatus} />
    </MissionStatusCard>

    <EnvironmentCard>
      <WindIndicator speed={windSpeed} direction={windDir} />
      <MetricCard label="Condition" value={condition} />
    </EnvironmentCard>

    <AlertsFeed>
      <AlertCard severity="CRITICAL" />
      <AlertCard severity="WARNING" />
      <AlertCard severity="INFO" />
    </AlertsFeed>
  </Grid>

  <MiniFieldMap>
    <FieldMap compact={true}>
      <DroneMarker /> (per drone)
    </FieldMap>
  </MiniFieldMap>
</DashboardPage>
```

### 2.2 FleetPage (/fleet)

```
<FleetPage>
  <ViewToggle options={["grid", "list"]} />

  <FleetGrid>
    <DroneCard droneId={1}>
      <DroneStateTag mode={mode} />
      <BatteryIndicator pct={battery} voltage={voltage} />
      <GPSIndicator available={gps} accuracy={accuracy} />
      <CommIndicator active={comm} />
      <StatusDot health={health} />
    </DroneCard>
    ... (per drone)
  </FleetGrid>

  <FleetSummary>
    <BatteryDistributionChart drones={droneStates} />
  </FleetSummary>
</FleetPage>
```

### 2.3 DroneDetailPage (/fleet/[droneId])

```
<DroneDetailPage droneId={id}>
  <BackButton to="/fleet" />
  <DroneHeader droneId={id} mode={mode} health={health} />

  <Grid cols={2}>
    <DroneDetailPanel>
      <MetricCard label="Armed" value={armed} />
      <MetricCard label="Mode" value={mode} />
      <MetricCard label="Health" value={health} />
      <MetricCard label="Task" value={currentTask} />
      <MetricCard label="Heading" value={headingDeg} />
    </DroneDetailPanel>

    <PositionMap>
      <FieldMap zoom={16}>
        <DroneMarker droneId={id} />
      </FieldMap>
      <MetricCard label="Lat" value={lat} />
      <MetricCard label="Lon" value={lon} />
      <MetricCard label="Alt" value={alt} />
    </PositionMap>

    <BatteryPanel>
      <BatteryIndicator pct={battery} voltage={voltage} large />
    </BatteryPanel>

    <VelocityPanel>
      <MetricCard label="Vx" value={vx} />
      <MetricCard label="Vy" value={vy} />
      <MetricCard label="Vz" value={vz} />
      <MetricCard label="Ground Speed" value={gs} />
    </VelocityPanel>
  </Grid>

  <TelemetryHistory>
    <BatteryChart droneId={id} />
    <AltitudeChart droneId={id} />
    <SpeedChart droneId={id} />
  </TelemetryHistory>
</DroneDetailPage>
```

### 2.4 MissionPage (/mission)

```
<MissionPage>
  <MissionHeader missionId={id} status={status} />

  <MissionTimeline>
    <ProgressBar progress={coveragePct} />
    <TimeMarkers start={startTime} current={now} end={estEnd} />
  </MissionTimeline>

  <Grid cols={2}>
    <TaskList>
      <TaskItem state="completed" />
      <TaskItem state="in_progress" />
      <TaskItem state="pending" />
    </TaskList>

    <EventLog>
      <EventEntry timestamp={ts} message={msg} />
      ... (time-ordered)
    </EventLog>
  </Grid>

  <CoverageChart>
    <CoverageChart data={coverageHistory} />
  </CoverageChart>
</MissionPage>
```

### 2.5 ReplayPage (/mission/replay)

```
<ReplayPage>
  <ReplayMap>
    <FieldMap>
      <DroneMarker /> (at selected frame positions)
      <FlightPathLayer /> (trajectory up to current frame)
    </FieldMap>
  </ReplayMap>

  <ReplayControls>
    <Button icon="skip-back" />
    <Button icon="step-back" />
    <Button icon="play" / icon="pause" />
    <Button icon="step-forward" />
    <Button icon="skip-forward" />
    <SpeedSelector options={[0.5, 1, 2, 4]} />
  </ReplayControls>

  <ReplayTimeline>
    <Scrubber frame={current} total={total} />
    <FrameInfo version={snapshotVersion} />
  </ReplayTimeline>

  <Grid cols={2}>
    <SnapshotList>
      <SnapshotItem version={v} timestamp={ts} selected={v === current} />
      ...
    </SnapshotList>

    <StateComparison>
      <SwarmStateSummary state={frameState} />
    </StateComparison>
  </Grid>
</ReplayPage>
```

### 2.6 MapPage (/map)

```
<MapPage>
  <FieldMap fullScreen={true}>
    <FarmPolygonLayer polygon={farmBoundary} />
    <MissionZoneLayer sectors={sectors} />
    <DroneMarker /> (per drone, color-coded)
    <FlightPathLayer /> (per drone trajectory)
    <FailureOverlay failures={activeFailures} />
    <WindIndicator speed={wind} direction={dir} />
  </FieldMap>

  <MapControls>
    <LayerToggle label="Drones" />
    <LayerToggle label="Paths" />
    <LayerToggle label="Zones" />
    <LayerToggle label="Wind" />
    <LayerToggle label="Failures" />
  </MapControls>

  <MapLegend>
    <LegendItem color="green" label="Active" />
    <LegendItem color="blue" label="Returning" />
    <LegendItem color="gray" label="Idle" />
    <LegendItem color="red" label="Fail" />
  </MapLegend>
</MapPage>
```

### 2.7 AlertsPage (/alerts)

```
<AlertsPage>
  <AlertFilterBar>
    <FilterButton label="All" />
    <FilterButton label="Critical" />
    <FilterButton label="Warning" />
    <FilterButton label="Info" />
    <FilterButton label="Resolved" />
  </AlertFilterBar>

  <AlertHistory>
    <AlertCard severity={sev} source={drone} message={msg} time={ts} />
    ...
  </AlertHistory>

  <AlertStatistics>
    <SeverityDistributionChart />
    <AlertTimelineChart />
  </AlertStatistics>
</AlertsPage>
```

---

## 3. Shared Components

| Component | Props | Purpose |
|-----------|-------|---------|
| `StatusDot` | `status: "ok" \| "warning" \| "critical" \| "offline"` | Color-coded circle |
| `MetricCard` | `label: string, value: string \| number, unit?: string` | Key-value display |
| `LiveBadge` | `connected: boolean` | WebSocket status badge |
| `TimeAgo` | `timestamp: number` | Relative time display |
| `LoadingSpinner` | `size?: "sm" \| "md" \| "lg"` | Loading indicator |
| `BatteryIndicator` | `pct: number, voltage: number, large?: boolean` | Battery bar + value |
| `GPSIndicator` | `available: boolean, accuracy: number` | GPS quality badge |
| `CommIndicator` | `active: boolean` | Communication status |
| `DroneStateTag` | `mode: DroneMode` | Mode badge with color |
| `SystemHealthBadge` | `health: HealthLevel` | OK / WARNING / CRITICAL badge |
| `WindIndicator` | `speed: number, direction: number` | Wind arrow + speed |

---

## 4. Color System

### 4.1 State Colors

| State | Color | Hex | Usage |
|-------|-------|-----|-------|
| Active / OK | Green | `#22C55E` | Healthy drones, OK health |
| Warning | Amber | `#F59E0B` | Low battery, degraded conditions |
| Critical / Fail | Red | `#EF4444` | Communication loss, critical failures |
| Idle / Standby | Gray | `#6B7280` | Inactive drones |
| Returning | Blue | `#3B82F6` | RTL or returning drones |
| Info | Blue | `#60A5FA` | Informational alerts |

### 4.2 Drone Map Markers

| Drone State | Marker Color | Marker Style |
|-------------|-------------|--------------|
| ACTIVE | Green | Solid circle with heading arrow |
| RETURNING | Blue | Solid circle with direction |
| IDLE | Gray | Hollow circle |
| FAIL | Red | Solid circle with pulse animation |
| Disconnected | Red outline | Dashed circle |
