import { create } from "zustand";
import type { MissionStatus } from "@/contracts/types";

export interface MissionEvent {
  readonly id: string;
  readonly timestamp_ms: number;
  readonly type: "START" | "PAUSE" | "RESUME" | "STOP" | "FAILURE" | "RECOVERY" | "MILESTONE";
  readonly message: string;
}

interface MissionStoreState {
  missionId: string | null;
  status: MissionStatus;
  progress: number;
  startTime: number | null;
  events: readonly MissionEvent[];
  setMission: (missionId: string | null, status: MissionStatus) => void;
  setProgress: (progress: number) => void;
  addEvent: (event: MissionEvent) => void;
  reset: () => void;
}

export const useMissionStore = create<MissionStoreState>((set) => ({
  missionId: null,
  status: "IDLE" as MissionStatus,
  progress: 0,
  startTime: null,
  events: [],

  setMission: (missionId: string | null, status: MissionStatus) =>
    set({
      missionId,
      status,
      startTime: status === "RUNNING" ? Date.now() : null,
    }),

  setProgress: (progress: number) => set({ progress }),

  addEvent: (event: MissionEvent) =>
    set((prev) => ({
      events: [...prev.events, event],
    })),

  reset: () =>
    set({
      missionId: null,
      status: "IDLE" as MissionStatus,
      progress: 0,
      startTime: null,
      events: [],
    }),
}));
