import { create } from "zustand";
import type { Alert, AlertSeverity } from "@/contracts/types";

interface AlertFilter {
  severity: AlertSeverity | "ALL";
  activeOnly: boolean;
}

interface AlertStoreState {
  alerts: readonly Alert[];
  unreadCount: number;
  filter: AlertFilter;
  addAlert: (alert: Alert) => void;
  resolveAlert: (alertId: string) => void;
  markAllRead: () => void;
  setFilter: (filter: Partial<AlertFilter>) => void;
  reset: () => void;
}

const MAX_ALERTS = 500;

export const useAlertStore = create<AlertStoreState>((set) => ({
  alerts: [],
  unreadCount: 0,
  filter: { severity: "ALL", activeOnly: false },

  addAlert: (alert: Alert) =>
    set((prev) => {
      const updated = [alert, ...prev.alerts].slice(0, MAX_ALERTS);
      return {
        alerts: updated,
        unreadCount: prev.unreadCount + 1,
      };
    }),

  resolveAlert: (alertId: string) =>
    set((prev) => ({
      alerts: prev.alerts.map((a) =>
        a.id === alertId
          ? { ...a, active: false, resolved_ms: Date.now() }
          : a
      ),
    })),

  markAllRead: () => set({ unreadCount: 0 }),

  setFilter: (filter: Partial<AlertFilter>) =>
    set((prev) => ({ filter: { ...prev.filter, ...filter } })),

  reset: () =>
    set({
      alerts: [],
      unreadCount: 0,
      filter: { severity: "ALL", activeOnly: false },
    }),
}));
