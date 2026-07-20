import { create } from "zustand";
import type { SwarmState } from "@/contracts/types";

interface SwarmStoreState {
  swarmState: SwarmState | null;
  lastVersion: number;
  setSwarmState: (state: SwarmState) => void;
  resetVersion: () => void;
  reset: () => void;
}

export const useSwarmStore = create<SwarmStoreState>((set) => ({
  swarmState: null,
  lastVersion: 0,

  setSwarmState: (state: SwarmState) =>
    set((prev) => {
      if (state.version < prev.lastVersion) return prev;
      return {
        swarmState: Object.freeze(state) as SwarmState,
        lastVersion: state.version,
      };
    }),

  // Accept the next frame regardless of version. Called on each WebSocket
  // (re)connect so a restarted backend (whose version counter resets) is not
  // rejected by the monotonic-version guard.
  resetVersion: () => set({ lastVersion: 0 }),

  reset: () =>
    set({
      swarmState: null,
      lastVersion: 0,
    }),
}));
