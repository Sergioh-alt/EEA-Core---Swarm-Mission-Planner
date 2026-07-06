"use client";

import { useWebSocket } from "@/hooks/useWebSocket";

interface ConnectionProviderProps {
  children: React.ReactNode;
}

export function ConnectionProvider({ children }: ConnectionProviderProps) {
  // Initialize WebSocket connection to Digital Twin
  useWebSocket();

  return <>{children}</>;
}
