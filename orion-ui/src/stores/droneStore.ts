import { create } from "zustand";
import type { DroneState } from "@/contracts/types";

interface DroneHistoryEntry {
  readonly timestamp_ms: number;
  readonly battery_pct: number;
  readonly altitude_m: number;
  readonly speed: number;
  readonly health: string;
}

interface DroneStoreState {
  drones: readonly DroneState[];
  selectedDroneId: number | null;
  droneHistories: Record<number, DroneHistoryEntry[]>;
  setDrones: (drones: readonly DroneState[]) => void;
  selectDrone: (droneId: number | null) => void;
  updateDrone: (drone: DroneState) => void;
  reset: () => void;
}

const MAX_HISTORY_LENGTH = 300;

export const useDroneStore = create<DroneStoreState>((set) => ({
  drones: [],
  selectedDroneId: null,
  droneHistories: {},

  setDrones: (drones: readonly DroneState[]) =>
    set((prev) => {
      const histories = { ...prev.droneHistories };
      for (const drone of drones) {
        const entry: DroneHistoryEntry = {
          timestamp_ms: drone.last_update_ms,
          battery_pct: drone.battery_pct,
          altitude_m: drone.position.altitude_m,
          speed: Math.sqrt(
            drone.velocity.vx ** 2 +
              drone.velocity.vy ** 2 +
              drone.velocity.vz ** 2
          ),
          health: drone.health,
        };
        const existing = histories[drone.drone_id] ?? [];
        histories[drone.drone_id] = [
          ...existing.slice(-MAX_HISTORY_LENGTH + 1),
          entry,
        ];
      }
      return { drones, droneHistories: histories };
    }),

  selectDrone: (droneId: number | null) =>
    set({ selectedDroneId: droneId }),

  updateDrone: (drone: DroneState) =>
    set((prev) => {
      const updated = prev.drones.map((d) =>
        d.drone_id === drone.drone_id ? drone : d
      );
      const histories = { ...prev.droneHistories };
      const entry: DroneHistoryEntry = {
        timestamp_ms: drone.last_update_ms,
        battery_pct: drone.battery_pct,
        altitude_m: drone.position.altitude_m,
        speed: Math.sqrt(
          drone.velocity.vx ** 2 +
            drone.velocity.vy ** 2 +
            drone.velocity.vz ** 2
        ),
        health: drone.health,
      };
      const existing = histories[drone.drone_id] ?? [];
      histories[drone.drone_id] = [
        ...existing.slice(-MAX_HISTORY_LENGTH + 1),
        entry,
      ];
      return { drones: updated, droneHistories: histories };
    }),

  reset: () =>
    set({ drones: [], selectedDroneId: null, droneHistories: {} }),
}));
