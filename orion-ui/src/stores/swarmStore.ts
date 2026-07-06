import { create } from "zustand";
import type { SwarmState, HealthLevel, MissionStatus, EnvironmentCondition } from "@/contracts/types";

interface SwarmStoreState {
  swarmState: SwarmState | null;
  lastVersion: number;
  setSwarmState: (state: SwarmState) => void;
  reset: () => void;
}

const INITIAL_SWARM_STATE: SwarmState = {
  swarm_id: "",
  timestamp_ms: 0,
  mission_status: "IDLE" as MissionStatus,
  mission_id: null,
  simulation_time_ms: 0,
  drone_states: [],
  global_health: "OK" as HealthLevel,
  active_failures: [],
  environment_state: {
    wind_speed_m_s: 0,
    wind_direction_deg: 0,
    condition: "NOMINAL" as EnvironmentCondition,
    timestamp_ms: 0,
  },
  total_drones: 0,
  active_drones: 0,
  failed_drones: 0,
  version: 0,
};

export const useSwarmStore = create<SwarmStoreState>((set) => ({
  swarmState: null,
  lastVersion: 0,

  setSwarmState: (state: SwarmState) =>
    set((prev) => {
      if (state.version <= prev.lastVersion) return prev;
      return {
        swarmState: Object.freeze(state) as SwarmState,
        lastVersion: state.version,
      };
    }),

  reset: () =>
    set({
      swarmState: INITIAL_SWARM_STATE,
      lastVersion: 0,
    }),
}));
