"use client";

import { cn } from "@/lib/utils";
import type { AlertSeverity } from "@/contracts/types";

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  INFO: "bg-blue-900/50 text-blue-300 border-blue-700",
  WARNING: "bg-amber-900/50 text-amber-300 border-amber-700",
  CRITICAL: "bg-red-900/50 text-red-300 border-red-700",
};

interface AlertBadgeProps {
  severity: AlertSeverity;
  count?: number;
  className?: string;
}

export function AlertBadge({ severity, count, className }: AlertBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        SEVERITY_STYLES[severity],
        className
      )}
    >
      {severity}
      {count !== undefined && count > 0 && (
        <span className="ml-0.5 rounded-full bg-white/10 px-1.5 py-0.5 text-[10px]">
          {count}
        </span>
      )}
    </span>
  );
}
