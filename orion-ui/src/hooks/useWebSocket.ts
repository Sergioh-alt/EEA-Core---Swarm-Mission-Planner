"use client";

import { useEffect, useRef } from "react";
import { getTwinWSClient, TwinWebSocketClient } from "@/lib/wsClient";

/**
 * Connects to the Digital Twin WebSocket when a backend URL is configured
 * via NEXT_PUBLIC_TWIN_WS_URL. When unset (local dev / validation with no
 * backend), the connection is skipped and the mock data provider supplies
 * state instead — avoiding noisy connection-refused errors.
 */
export function useWebSocket(baseUrl?: string): TwinWebSocketClient {
  const resolvedBaseUrl = baseUrl ?? process.env.NEXT_PUBLIC_TWIN_WS_URL;
  const clientRef = useRef<TwinWebSocketClient>(
    getTwinWSClient(resolvedBaseUrl)
  );

  useEffect(() => {
    if (!resolvedBaseUrl) return;
    const client = clientRef.current;
    client.connect();
    return () => {
      client.disconnect();
    };
  }, [resolvedBaseUrl]);

  return clientRef.current;
}
