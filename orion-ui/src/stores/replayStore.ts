import { create } from "zustand";
import type { ReplayTimeline, ReplayFrame } from "@/contracts/types";

interface ReplayStoreState {
  timeline: ReplayTimeline | null;
  currentFrameIndex: number;
  playing: boolean;
  speed: number;
  currentFrame: ReplayFrame | null;
  setTimeline: (timeline: ReplayTimeline) => void;
  setFrameIndex: (index: number) => void;
  play: () => void;
  pause: () => void;
  setSpeed: (speed: number) => void;
  reset: () => void;
}

export const useReplayStore = create<ReplayStoreState>((set, get) => ({
  timeline: null,
  currentFrameIndex: 0,
  playing: false,
  speed: 1,
  currentFrame: null,

  setTimeline: (timeline: ReplayTimeline) =>
    set({
      timeline,
      currentFrameIndex: 0,
      currentFrame: timeline.frames[0] ?? null,
      playing: false,
    }),

  setFrameIndex: (index: number) => {
    const { timeline } = get();
    if (!timeline) return;
    const clamped = Math.max(0, Math.min(index, timeline.total_frames - 1));
    set({
      currentFrameIndex: clamped,
      currentFrame: timeline.frames[clamped] ?? null,
    });
  },

  play: () => set({ playing: true }),
  pause: () => set({ playing: false }),

  setSpeed: (speed: number) =>
    set({ speed: Math.max(0.25, Math.min(speed, 8)) }),

  reset: () =>
    set({
      timeline: null,
      currentFrameIndex: 0,
      playing: false,
      speed: 1,
      currentFrame: null,
    }),
}));
