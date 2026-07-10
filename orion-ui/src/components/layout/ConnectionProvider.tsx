"use client";

import { useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useConnectionStore } from "@/stores/connectionStore";
import { startMockDataProvider, stopMockDataProvider, isMockRunning } from "@/lib/mockDataProvider";

interface ConnectionProviderProps {
  children: React.ReactNode;
}

export function ConnectionProvider({ children }: ConnectionProviderProps) {
  // Initialize WebSocket connection to Digital Twin
  useWebSocket();

  useEffect(() => {
    // Start mock data provider when no real WebSocket backend is available.
    // In production, the WebSocket hook connects to the Digital Twin and
    // the mock provider remains dormant.
    // Runs once on mount; the guard prevents duplicate intervals.
    const timer = setTimeout(() => {
      const status = useConnectionStore.getState().status;
      if (status !== "CONNECTED" && !isMockRunning()) {
        startMockDataProvider();
      }
    }, 1000);

    return () => {
      clearTimeout(timer);
      stopMockDataProvider();
    };
  }, []);

  return <>{children}</>;
}
