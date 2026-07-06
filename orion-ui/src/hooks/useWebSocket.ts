"use client";

import { useEffect, useRef } from "react";
import { getTwinWSClient, TwinWebSocketClient } from "@/lib/wsClient";

export function useWebSocket(baseUrl?: string): TwinWebSocketClient {
  const clientRef = useRef<TwinWebSocketClient>(getTwinWSClient(baseUrl));

  useEffect(() => {
    const client = clientRef.current;
    client.connect();
    return () => {
      client.disconnect();
    };
  }, []);

  return clientRef.current;
}
