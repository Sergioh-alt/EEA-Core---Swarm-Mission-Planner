"use client";

import { cn } from "@/lib/utils";
import { useConnectionStore } from "@/stores/connectionStore";
import type { ConnectionStatus } from "@/stores/connectionStore";

const STATUS_STYLES: Record<
  ConnectionStatus,
  { dot: string; text: string; label: string }
> = {
  CONNECTED: {
    dot: "bg-emerald-500",
    text: "text-emerald-400",
    label: "Connected",
  },
  CONNECTING: {
    dot: "bg-amber-500 animate-pulse",
    text: "text-amber-400",
    label: "Connecting...",
  },
  DISCONNECTED: {
    dot: "bg-neutral-600",
    text: "text-neutral-500",
    label: "Disconnected",
  },
  ERROR: {
    dot: "bg-red-500 animate-pulse",
    text: "text-red-400",
    label: "Error",
  },
};

interface ConnectionBadgeProps {
  className?: string;
}

export function ConnectionBadge({ className }: ConnectionBadgeProps) {
  const status = useConnectionStore((s) => s.status);
  const latencyMs = useConnectionStore((s) => s.latencyMs);
  const style = STATUS_STYLES[status];

  return (
    <div className={cn("flex items-center gap-2 text-xs", className)}>
      <span className={cn("h-2 w-2 rounded-full", style.dot)} />
      <span className={style.text}>{style.label}</span>
      {status === "CONNECTED" && latencyMs > 0 && (
        <span className="text-neutral-600 font-mono">{latencyMs}ms</span>
      )}
    </div>
  );
}
