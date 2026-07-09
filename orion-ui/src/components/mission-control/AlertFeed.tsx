"use client";

import { useAlertStore } from "@/stores/alertStore";
import { cn, formatTimestamp } from "@/lib/utils";
import type { Alert, AlertSeverity } from "@/contracts/types";
import { AlertTriangle, Info, AlertCircle, Bell } from "lucide-react";

const SEVERITY_CONFIG: Record<
  AlertSeverity,
  { icon: React.ReactNode; color: string; bg: string; border: string }
> = {
  INFO: {
    icon: <Info className="h-3 w-3" />,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
  },
  WARNING: {
    icon: <AlertTriangle className="h-3 w-3" />,
    color: "text-yellow-400",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/20",
  },
  CRITICAL: {
    icon: <AlertCircle className="h-3 w-3" />,
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/20",
  },
};

export function AlertFeed() {
  const alerts = useAlertStore((s) => s.alerts);
  const unreadCount = useAlertStore((s) => s.unreadCount);
  const markAllRead = useAlertStore((s) => s.markAllRead);

  const recentAlerts = alerts.slice(0, 30);

  return (
    <div className="flex flex-col h-full rounded-lg bg-neutral-900/50 border border-neutral-800 overflow-hidden">
      <div className="px-3 py-2.5 border-b border-neutral-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
            Alerts
          </h2>
          {unreadCount > 0 && (
            <span className="rounded-full bg-red-500/20 text-red-400 px-1.5 py-0.5 text-[9px] font-medium">
              {unreadCount}
            </span>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={markAllRead}
            className="text-[10px] text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Mark read
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {recentAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-neutral-600">
            <Bell className="h-5 w-5 mb-2" />
            <p className="text-[10px]">No alerts</p>
          </div>
        ) : (
          <div className="space-y-0.5 p-1.5">
            {recentAlerts.map((alert: Alert) => (
              <AlertItem key={alert.id} alert={alert} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AlertItem({ alert }: { alert: Alert }) {
  const config = SEVERITY_CONFIG[alert.severity];

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md px-2.5 py-2 border transition-colors",
        config.bg,
        config.border,
        !alert.active && "opacity-50"
      )}
    >
      <div className={cn("mt-0.5", config.color)}>{config.icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] text-neutral-300 leading-tight">
          {alert.message}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[9px] text-neutral-600">
            {formatTimestamp(alert.timestamp_ms)}
          </span>
          <span className="text-[9px] text-neutral-600">
            {alert.source}
          </span>
          {!alert.active && (
            <span className="text-[9px] text-green-600">resolved</span>
          )}
        </div>
      </div>
      <span
        className={cn(
          "text-[8px] font-bold uppercase px-1 py-0.5 rounded",
          config.color
        )}
      >
        {alert.severity}
      </span>
    </div>
  );
}
