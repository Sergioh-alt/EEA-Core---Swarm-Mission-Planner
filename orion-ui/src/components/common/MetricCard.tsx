"use client";

import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: "up" | "down" | "stable";
  className?: string;
}

export function MetricCard({
  label,
  value,
  icon,
  trend,
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-neutral-800 bg-neutral-900 p-4",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">
          {label}
        </span>
        {icon && <span className="text-neutral-500">{icon}</span>}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-neutral-100">{value}</span>
        {trend && (
          <span
            className={cn(
              "text-xs font-medium",
              trend === "up" && "text-emerald-400",
              trend === "down" && "text-red-400",
              trend === "stable" && "text-neutral-500"
            )}
          >
            {trend === "up" ? "\u2191" : trend === "down" ? "\u2193" : "\u2014"}
          </span>
        )}
      </div>
    </div>
  );
}
