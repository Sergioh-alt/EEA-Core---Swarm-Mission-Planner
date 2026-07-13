"use client";

import { useEffect, useRef } from "react";
import { getTwinWSClient, TwinWebSocketClient } from "@/lib/wsClient";
import { wsBaseUrl, isLiveMode } from "@/lib/config";

/**
 * Connects to the Digital Twin WebSocket when a backend is configured via
 * NEXT_PUBLIC_TWIN_API_URL (LIVE mode). When unset (local dev / validation
 * with no backend), the connection is skipped and the development-only mock
 * data provider supplies state instead — avoiding connection-refused noise.
 */
export function useWebSocket(baseUrl?: string): TwinWebSocketClient {
  const resolvedBaseUrl = baseUrl ?? wsBaseUrl();
  const clientRef = useRef<TwinWebSocketClient>(
    getTwinWSClient(resolvedBaseUrl)
  );

  useEffect(() => {
    if (!isLiveMode() && !baseUrl) return;
    const client = clientRef.current;
    client.connect();
    return () => {
      client.disconnect();
    };
  }, [baseUrl]);

  return clientRef.current;
}
