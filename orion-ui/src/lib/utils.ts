import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

export function formatTimestamp(ms: number): string {
  return new Date(ms).toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

export function formatBattery(pct: number): string {
  return `${Math.round(pct)}%`;
}

export function formatCoordinate(value: number, decimals = 6): string {
  return value.toFixed(decimals);
}

export function formatAltitude(meters: number): string {
  return `${meters.toFixed(1)}m`;
}

export function formatSpeed(mps: number): string {
  return `${mps.toFixed(1)} m/s`;
}
