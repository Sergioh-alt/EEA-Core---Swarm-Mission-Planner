"use client";

import { useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { isLiveMode } from "@/lib/config";
import { startMockDataProvider, stopMockDataProvider, isMockRunning } from "@/lib/mockDataProvider";

interface ConnectionProviderProps {
  children: React.ReactNode;
}

export function ConnectionProvider({ children }: ConnectionProviderProps) {
  // LIVE mode: connect to the real Digital Twin API over WebSocket.
  useWebSocket();

  useEffect(() => {
    // Development-only fallback: when no Digital Twin API server is configured
    // (NEXT_PUBLIC_TWIN_API_URL unset), the mock provider supplies state so a
    // fresh clone still renders. In LIVE mode the mock never starts — the UI
    // is driven entirely by the Digital Twin.
    if (isLiveMode()) return;

    if (!isMockRunning()) {
      startMockDataProvider();
    }

    return () => {
      stopMockDataProvider();
    };
  }, []);

  return <>{children}</>;
}
