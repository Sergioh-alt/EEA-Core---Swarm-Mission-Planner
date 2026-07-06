import { create } from "zustand";
import type { SwarmState } from "@/contracts/types";

interface SwarmStoreState {
  swarmState: SwarmState | null;
  lastVersion: number;
  setSwarmState: (state: SwarmState) => void;
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

  reset: () =>
    set({
      swarmState: null,
      lastVersion: 0,
    }),
}));
