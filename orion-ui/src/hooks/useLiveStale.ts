"use client";

import { useConnectionStore } from "@/stores/connectionStore";
import { isLiveMode } from "@/lib/config";

/**
 * True when the Digital Twin connection is down while running against a
 * backend, meaning every value in the runtime stores is the last frame that
 * arrived before the link dropped.
 *
 * Mission Control shows the Digital Twin's state and nothing else, so while the
 * link is down it must present that state as last-known rather than live —
 * a frozen RUNNING mission with moving drones would be fiction. No decision is
 * made here: the UI only stops claiming freshness it cannot verify.
 */
export function useLiveStale(): boolean {
  const status = useConnectionStore((s) => s.status);
  if (!isLiveMode()) return false;
  return status === "DISCONNECTED" || status === "ERROR";
}
