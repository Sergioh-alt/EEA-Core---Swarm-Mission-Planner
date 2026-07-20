/**
 * WebSocket client for Digital Twin real-time state streaming.
 *
 * Connects to the Digital Twin WebSocket endpoint only.
 * Never communicates with PX4, ROS2, MAVLink, Hive, or any execution layer.
 */

import { WS_ENDPOINT } from "@/contracts/api";
import type { ServerMessage, ClientMessage } from "@/contracts/api";
import type { SwarmState, Alert, DroneState, MissionInfo } from "@/contracts/types";
import { useSwarmStore } from "@/stores/swarmStore";
import { useDroneStore } from "@/stores/droneStore";
import { useAlertStore } from "@/stores/alertStore";
import { useMissionStore } from "@/stores/missionStore";
import { useConnectionStore } from "@/stores/connectionStore";
import type { ConnectionStatus } from "@/stores/connectionStore";

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;
// Bound de-duplication memory so long-running sessions do not grow unbounded.
const MAX_SEEN_EVENT_IDS = 2000;

export class TwinWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private seenEventIds = new Set<string>();

  constructor(baseUrl?: string) {
    const wsBase = baseUrl ?? this.inferWsUrl();
    this.url = `${wsBase}${WS_ENDPOINT}`;
  }

  private inferWsUrl(): string {
    if (typeof window === "undefined") return "ws://localhost:8000";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }

  connect(): void {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this.shouldReconnect = true;
    this.updateStatus("CONNECTING");

    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
    } catch {
      this.updateStatus("ERROR");
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }
    this.updateStatus("DISCONNECTED");
  }

  /**
   * Operator-initiated recovery: clear any pending backoff, reset the
   * attempt counter, and reconnect immediately. Used when automatic
   * reconnection has been exhausted.
   */
  reconnectNow(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    useConnectionStore.getState().resetReconnect();
    this.connect();
  }

  send(message: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private handleOpen(): void {
    this.updateStatus("CONNECTED");
    useConnectionStore.getState().resetReconnect();
    // A fresh connection may be to a restarted backend whose state version
    // counter has reset; accept its next frame instead of rejecting it.
    useSwarmStore.getState().resetVersion();
  }

  private handleMessage(event: MessageEvent): void {
    useConnectionStore.getState().recordMessage();

    try {
      const message = JSON.parse(event.data as string) as ServerMessage;
      this.routeMessage(message);
    } catch {
      // Malformed message — ignore silently
    }
  }

  private routeMessage(message: ServerMessage): void {
    switch (message.type) {
      case "SWARM_STATE": {
        const swarmState = message.payload as SwarmState;
        useSwarmStore.getState().setSwarmState(swarmState);
        useDroneStore.getState().setDrones(swarmState.drone_states);
        break;
      }
      case "DRONE_STATE_DELTA": {
        const droneState = message.payload as DroneState;
        useDroneStore.getState().updateDrone(droneState);
        break;
      }
      case "MISSION_STATUS": {
        const mission = message.payload as MissionInfo;
        const store = useMissionStore.getState();
        store.setMission(mission.mission_id, mission.status);
        store.setProgress(mission.progress);
        for (const evt of mission.events) {
          if (!this.seenEventIds.has(evt.id)) {
            this.seenEventIds.add(evt.id);
            this.trimSeenEventIds();
            store.addEvent(evt);
          }
        }
        break;
      }
      case "ALERT": {
        const alert = message.payload as Alert;
        useAlertStore.getState().addAlert(alert);
        break;
      }
      case "CONNECTION_STATUS": {
        const latency = (message.payload as { latency_ms: number }).latency_ms;
        useConnectionStore.getState().setLatency(latency);
        break;
      }
    }
  }

  private handleClose(): void {
    this.ws = null;
    this.updateStatus("DISCONNECTED");
    if (this.shouldReconnect) {
      this.scheduleReconnect();
    }
  }

  private handleError(): void {
    this.updateStatus("ERROR");
  }

  private scheduleReconnect(): void {
    const store = useConnectionStore.getState();
    if (store.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;

    store.incrementReconnect();
    const delay = Math.min(
      BASE_RECONNECT_DELAY_MS * 2 ** store.reconnectAttempts,
      MAX_RECONNECT_DELAY_MS
    );

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private trimSeenEventIds(): void {
    if (this.seenEventIds.size <= MAX_SEEN_EVENT_IDS) return;
    const overflow = this.seenEventIds.size - MAX_SEEN_EVENT_IDS;
    const iterator = this.seenEventIds.values();
    for (let i = 0; i < overflow; i++) {
      const next = iterator.next();
      if (next.done) break;
      this.seenEventIds.delete(next.value);
    }
  }

  private updateStatus(status: ConnectionStatus): void {
    useConnectionStore.getState().setStatus(status);
  }
}

let clientInstance: TwinWebSocketClient | null = null;

export function getTwinWSClient(baseUrl?: string): TwinWebSocketClient {
  if (!clientInstance) {
    clientInstance = new TwinWebSocketClient(baseUrl);
  }
  return clientInstance;
}
