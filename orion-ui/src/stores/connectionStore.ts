import { create } from "zustand";

export type ConnectionStatus = "CONNECTED" | "CONNECTING" | "DISCONNECTED" | "ERROR";

interface ConnectionStoreState {
  status: ConnectionStatus;
  latencyMs: number;
  lastMessageMs: number;
  reconnectAttempts: number;
  setStatus: (status: ConnectionStatus) => void;
  setLatency: (latencyMs: number) => void;
  recordMessage: () => void;
  incrementReconnect: () => void;
  resetReconnect: () => void;
  reset: () => void;
}

export const useConnectionStore = create<ConnectionStoreState>((set) => ({
  status: "DISCONNECTED",
  latencyMs: 0,
  lastMessageMs: 0,
  reconnectAttempts: 0,

  setStatus: (status: ConnectionStatus) => set({ status }),
  setLatency: (latencyMs: number) => set({ latencyMs }),
  recordMessage: () => set({ lastMessageMs: Date.now() }),
  incrementReconnect: () =>
    set((prev) => ({ reconnectAttempts: prev.reconnectAttempts + 1 })),
  resetReconnect: () => set({ reconnectAttempts: 0 }),
  reset: () =>
    set({
      status: "DISCONNECTED",
      latencyMs: 0,
      lastMessageMs: 0,
      reconnectAttempts: 0,
    }),
}));
