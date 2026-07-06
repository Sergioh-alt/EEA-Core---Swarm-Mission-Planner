"use client";

import { PageShell } from "@/components/common/PageShell";
import { ConnectionBadge } from "@/components/common/ConnectionBadge";
import { useConnectionStore } from "@/stores/connectionStore";

export default function SettingsPage() {
  const latencyMs = useConnectionStore((s) => s.latencyMs);
  const reconnectAttempts = useConnectionStore((s) => s.reconnectAttempts);

  return (
    <PageShell title="Settings" description="System configuration and status">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 max-w-4xl">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Connection
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Status</span>
              <ConnectionBadge />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Latency</span>
              <span className="text-xs font-mono text-neutral-300">
                {latencyMs > 0 ? `${latencyMs}ms` : "--"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Reconnect Attempts</span>
              <span className="text-xs font-mono text-neutral-300">
                {reconnectAttempts}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Display
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Theme</span>
              <span className="text-xs font-mono text-neutral-300">Dark</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Update Rate</span>
              <span className="text-xs font-mono text-neutral-300">1 Hz</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Version</span>
              <span className="text-xs font-mono text-neutral-300">
                10C.2
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Architecture Info
          </h2>
          <div className="space-y-2 text-xs text-neutral-500">
            <p>Data Source: Digital Twin (read-only)</p>
            <p>Real-time Channel: WebSocket</p>
            <p>On-demand Channel: REST API</p>
            <p>Write Path: Intent submission only</p>
            <p>Decision Authority: Hive (via backend handler)</p>
          </div>
        </div>

        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <h2 className="text-sm font-medium text-neutral-300 mb-3">
            Map Configuration
          </h2>
          <div className="space-y-2 text-xs text-neutral-500">
            <p>Provider: Mapbox GL (pending configuration)</p>
            <p>Default Zoom: 15</p>
            <p>Marker Clustering: Enabled for 20+ drones</p>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
