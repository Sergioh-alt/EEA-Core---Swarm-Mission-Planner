"use client";

import { useRef } from "react";
import { getTwinRESTClient, TwinRESTClient } from "@/lib/restClient";

export function useRESTClient(baseUrl?: string): TwinRESTClient {
  const clientRef = useRef<TwinRESTClient>(getTwinRESTClient(baseUrl));
  return clientRef.current;
}
