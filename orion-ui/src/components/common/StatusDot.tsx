"use client";

import { cn } from "@/lib/utils";
import type { HealthLevel } from "@/contracts/types";

const STATUS_COLORS: Record<HealthLevel, string> = {
  OK: "bg-emerald-500",
  WARNING: "bg-amber-500",
  CRITICAL: "bg-red-500",
};

const PULSE_CLASSES: Record<HealthLevel, string> = {
  OK: "",
  WARNING: "animate-pulse",
  CRITICAL: "animate-pulse",
};

interface StatusDotProps {
  health: HealthLevel;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

const SIZE_CLASSES = {
  sm: "h-2 w-2",
  md: "h-3 w-3",
  lg: "h-4 w-4",
};

export function StatusDot({
  health,
  size = "md",
  showLabel = false,
  className,
}: StatusDotProps) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className={cn(
          "rounded-full",
          SIZE_CLASSES[size],
          STATUS_COLORS[health],
          PULSE_CLASSES[health]
        )}
      />
      {showLabel && (
        <span className="text-xs font-medium text-neutral-300">{health}</span>
      )}
    </span>
  );
}
