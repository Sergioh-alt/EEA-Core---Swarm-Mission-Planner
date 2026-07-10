"use client";

import { cn } from "@/lib/utils";

interface BatteryIndicatorProps {
  percentage: number;
  voltage?: number;
  showLabel?: boolean;
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
}

function getBatteryColor(pct: number): string {
  if (pct > 60) return "bg-emerald-500";
  if (pct > 30) return "bg-amber-500";
  return "bg-red-500";
}

const BAR_HEIGHTS = {
  xs: "h-1.5",
  sm: "h-2",
  md: "h-3",
  lg: "h-4",
};

export function BatteryIndicator({
  percentage,
  voltage,
  showLabel = true,
  size = "md",
  className,
}: BatteryIndicatorProps) {
  const clamped = Math.max(0, Math.min(100, percentage));

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn(
          "relative w-16 rounded-sm bg-neutral-800",
          BAR_HEIGHTS[size]
        )}
      >
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-sm transition-all",
            getBatteryColor(clamped)
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono text-neutral-300">
          {Math.round(clamped)}%
          {voltage !== undefined && (
            <span className="text-neutral-500 ml-1">
              {voltage.toFixed(1)}V
            </span>
          )}
        </span>
      )}
    </div>
  );
}
