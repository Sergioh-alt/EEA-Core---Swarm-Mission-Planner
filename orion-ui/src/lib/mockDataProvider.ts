/**
 * Phase 10C.3 — Mock Data Provider
 *
 * Simulates 2-3 drones with realistic telemetry updates at ~1 Hz.
 * Used for UI development/validation when no backend Digital Twin is connected.
 * Data flows through the same Zustand stores as real WebSocket data.
 */

import { useSwarmStore } from "@/stores/swarmStore";
import { useDroneStore } from "@/stores/droneStore";
import { useMissionStore, type MissionEvent } from "@/stores/missionStore";
import { useAlertStore } from "@/stores/alertStore";
import { useConnectionStore } from "@/stores/connectionStore";
import {
  type SwarmState,
  type DroneState,
  type Alert,
  MissionStatus,
  DroneMode,
  HealthLevel,
  TaskState,
  FailureCategory,
  EnvironmentCondition,
} from "@/contracts/types";

const FIELD_CENTER = { lat: 38.7223, lng: -9.1393 };
const NUM_DRONES = 3;

interface DroneSimState {
  drone_id: number;
  lat: number;
  lng: number;
  alt: number;
  heading: number;
  battery: number;
  speed: number;
  phase: number;
  routeProgress: number;
}

let simDrones: DroneSimState[] = [];
let simVersion = 0;
let simTime = 0;
let intervalId: ReturnType<typeof setInterval> | null = null;
let missionStarted = false;
let alertCounter = 0;

function initSimDrones(): void {
  simDrones = [];
  for (let i = 0; i < NUM_DRONES; i++) {
    simDrones.push({
      drone_id: i + 1,
      lat: FIELD_CENTER.lat + (i - 1) * 0.001,
      lng: FIELD_CENTER.lng + (i - 1) * 0.0005,
      alt: 20 + i * 5,
      heading: 90 + i * 30,
      battery: 100 - i * 3,
      speed: 2 + i * 0.5,
      phase: i * (Math.PI / 3),
      routeProgress: 0,
    });
  }
}

function generateRoute(droneId: number): Array<{ lat: number; lng: number }> {
  const offset = (droneId - 1) * 0.002;
  const route: Array<{ lat: number; lng: number }> = [];
  const rows = 6;
  const colSpan = 0.004;

  for (let r = 0; r < rows; r++) {
    const startLng = FIELD_CENTER.lng - colSpan / 2 + offset;
    const endLng = FIELD_CENTER.lng + colSpan / 2 + offset;
    const lat = FIELD_CENTER.lat - 0.003 + r * 0.001;

    if (r % 2 === 0) {
      route.push({ lat, lng: startLng });
      route.push({ lat, lng: endLng });
    } else {
      route.push({ lat, lng: endLng });
      route.push({ lat, lng: startLng });
    }
  }
  return route;
}

function updateDronePosition(drone: DroneSimState, dt: number): void {
  drone.phase += dt * 0.3;
  drone.routeProgress = Math.min(drone.routeProgress + dt * 0.02, 1);
  const radius = 0.002;
  drone.lat =
    FIELD_CENTER.lat +
    (drone.drone_id - 2) * 0.001 +
    Math.sin(drone.phase) * radius;
  drone.lng =
    FIELD_CENTER.lng +
    (drone.drone_id - 2) * 0.0005 +
    Math.cos(drone.phase) * radius;
  drone.alt = 20 + drone.drone_id * 5 + Math.sin(drone.phase * 0.5) * 2;
  drone.heading = ((drone.heading + dt * 10) % 360 + 360) % 360;
  drone.battery = Math.max(0, drone.battery - dt * 0.03);
  drone.speed = 2 + drone.drone_id * 0.5 + Math.sin(drone.phase) * 0.3;
}

function buildDroneState(sim: DroneSimState): DroneState {
  const health =
    sim.battery < 20
      ? HealthLevel.CRITICAL
      : sim.battery < 50
        ? HealthLevel.WARNING
        : HealthLevel.OK;

  return {
    drone_id: sim.drone_id,
    armed: true,
    mode: DroneMode.AUTO,
    position: {
      latitude: sim.lat,
      longitude: sim.lng,
      altitude_m: sim.alt,
    },
    velocity: {
      vx: sim.speed * Math.cos((sim.heading * Math.PI) / 180),
      vy: sim.speed * Math.sin((sim.heading * Math.PI) / 180),
      vz: Math.sin(sim.phase * 0.5) * 0.2,
    },
    heading_deg: sim.heading,
    battery_pct: sim.battery,
    battery_voltage: 11.1 + (sim.battery / 100) * 5.5,
    gps_available: true,
    gps_accuracy_m: 1.2 + Math.random() * 0.5,
    communication_active: true,
    health,
    current_task: TaskState.IN_PROGRESS,
    last_update_ms: Date.now(),
  };
}

function buildSwarmState(drones: DroneState[]): SwarmState {
  simVersion++;
  const failedCount = drones.filter(
    (d) => d.health === HealthLevel.CRITICAL
  ).length;
  const globalHealth =
    failedCount > 0
      ? HealthLevel.CRITICAL
      : drones.some((d) => d.health === HealthLevel.WARNING)
        ? HealthLevel.WARNING
        : HealthLevel.OK;

  return {
    swarm_id: "swarm-orion-001",
    timestamp_ms: Date.now(),
    mission_status: missionStarted ? MissionStatus.RUNNING : MissionStatus.IDLE,
    mission_id: missionStarted ? "mission-alpha-001" : null,
    simulation_time_ms: simTime * 1000,
    drone_states: drones,
    global_health: globalHealth,
    active_failures: [],
    environment_state: {
      wind_speed_m_s: 3.2 + Math.sin(simTime * 0.1) * 1.5,
      wind_direction_deg: 180 + Math.sin(simTime * 0.05) * 30,
      condition: EnvironmentCondition.NOMINAL,
      timestamp_ms: Date.now(),
    },
    total_drones: NUM_DRONES,
    active_drones: drones.filter((d) => d.communication_active).length,
    failed_drones: failedCount,
    version: simVersion,
  };
}

function maybeGenerateAlert(): void {
  if (Math.random() > 0.02) return;
  alertCounter++;
  const severities = ["INFO", "WARNING", "CRITICAL"] as const;
  const severity = severities[Math.floor(Math.random() * 3)];
  const messages = [
    "Battery level dropping on Drone 2",
    "GPS accuracy degraded",
    "Wind speed increasing",
    "Telemetry latency spike detected",
    "Drone 1 approaching boundary",
    "Mission checkpoint reached",
  ];
  const alert: Alert = {
    id: `alert-${alertCounter}`,
    severity,
    source: `drone_${Math.floor(Math.random() * NUM_DRONES) + 1}`,
    message: messages[Math.floor(Math.random() * messages.length)],
    category: "SYSTEM",
    timestamp_ms: Date.now(),
    active: true,
    resolved_ms: null,
  };
  useAlertStore.getState().addAlert(alert);
}

function tick(): void {
  const dt = 1;
  simTime += dt;

  for (const drone of simDrones) {
    updateDronePosition(drone, dt);
  }

  const droneStates = simDrones.map(buildDroneState);
  const swarmState = buildSwarmState(droneStates);

  useSwarmStore.getState().setSwarmState(swarmState);
  useDroneStore.getState().setDrones(droneStates);

  if (!missionStarted && simTime === 3) {
    missionStarted = true;
    useMissionStore.getState().setMission("mission-alpha-001", MissionStatus.RUNNING);
    useMissionStore.getState().setProgress(0);
    const event: MissionEvent = {
      id: `evt-start`,
      timestamp_ms: Date.now(),
      type: "START",
      message: "Mission Alpha-001 started — 3 drones deployed",
    };
    useMissionStore.getState().addEvent(event);
  }

  if (missionStarted) {
    const progress = Math.min((simTime - 3) / 120, 1);
    useMissionStore.getState().setProgress(progress);

    if (simTime % 30 === 0 && simTime < 120) {
      const event: MissionEvent = {
        id: `evt-milestone-${simTime}`,
        timestamp_ms: Date.now(),
        type: "MILESTONE",
        message: `Coverage: ${Math.round(progress * 100)}% complete`,
      };
      useMissionStore.getState().addEvent(event);
    }
  }

  maybeGenerateAlert();

  useConnectionStore.getState().setLatency(Math.floor(15 + Math.random() * 10));
  useConnectionStore.getState().recordMessage();
}

export function getFieldPolygon(): Array<{ lat: number; lng: number }> {
  return [
    { lat: FIELD_CENTER.lat - 0.004, lng: FIELD_CENTER.lng - 0.005 },
    { lat: FIELD_CENTER.lat - 0.004, lng: FIELD_CENTER.lng + 0.005 },
    { lat: FIELD_CENTER.lat + 0.004, lng: FIELD_CENTER.lng + 0.005 },
    { lat: FIELD_CENTER.lat + 0.004, lng: FIELD_CENTER.lng - 0.005 },
  ];
}

export function getPlannedRoutes(): Record<
  number,
  Array<{ lat: number; lng: number }>
> {
  const routes: Record<number, Array<{ lat: number; lng: number }>> = {};
  for (let i = 1; i <= NUM_DRONES; i++) {
    routes[i] = generateRoute(i);
  }
  return routes;
}

export function getFieldCenter(): { lat: number; lng: number } {
  return { ...FIELD_CENTER };
}

export function startMockDataProvider(): void {
  if (intervalId !== null) return;

  initSimDrones();
  simVersion = 0;
  simTime = 0;
  missionStarted = false;
  alertCounter = 0;

  useConnectionStore.getState().setStatus("CONNECTED");

  tick();
  intervalId = setInterval(tick, 1000);
}

export function stopMockDataProvider(): void {
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

export function isMockRunning(): boolean {
  return intervalId !== null;
}

export function injectFailure(
  droneId: number,
  failure: FailureCategory
): void {
  const drone = simDrones.find((d) => d.drone_id === droneId);
  if (!drone) return;

  switch (failure) {
    case FailureCategory.BATTERY_DEGRADATION:
      drone.battery = Math.max(0, drone.battery - 30);
      break;
    case FailureCategory.GPS_LOSS:
      break;
    case FailureCategory.LINK_LOSS:
      break;
    case FailureCategory.WIND_DISTURBANCE:
      break;
  }

  const alert: Alert = {
    id: `alert-fail-${++alertCounter}`,
    severity: "CRITICAL",
    source: `drone_${droneId}`,
    message: `Failure injected: ${failure} on Drone ${droneId}`,
    category: failure,
    timestamp_ms: Date.now(),
    active: true,
    resolved_ms: null,
  };
  useAlertStore.getState().addAlert(alert);
}
