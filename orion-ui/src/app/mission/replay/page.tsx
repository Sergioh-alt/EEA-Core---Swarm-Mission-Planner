"use client";

import { useEffect, useRef, useState } from "react";
import { PageShell } from "@/components/common/PageShell";
import { useReplayStore } from "@/stores/replayStore";
import { getTwinRESTClient } from "@/lib/restClient";
import { isLiveMode } from "@/lib/config";
import { HealthLevel } from "@/contracts/types";
import type { DroneState } from "@/contracts/types";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Rewind,
  FastForward,
  Loader2,
} from "lucide-react";

const HEALTH_COLORS: Record<string, string> = {
  [HealthLevel.OK]: "#22c55e",
  [HealthLevel.WARNING]: "#f59e0b",
  [HealthLevel.CRITICAL]: "#ef4444",
};

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString(undefined, {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Read-only scatter of frame drone positions, normalized to frame bounds. */
function FrameScatter({ drones }: { drones: readonly DroneState[] }) {
  const pts = drones.filter(
    (d) => d.position.latitude !== 0 || d.position.longitude !== 0
  );
  if (pts.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-neutral-600 text-sm">
        No positioned drones in this frame
      </div>
    );
  }
  const lats = pts.map((d) => d.position.latitude);
  const lngs = pts.map((d) => d.position.longitude);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const spanLat = maxLat - minLat || 1;
  const spanLng = maxLng - minLng || 1;
  const px = (lng: number) => 10 + ((lng - minLng) / spanLng) * 80;
  const py = (lat: number) => 90 - ((lat - minLat) / spanLat) * 80;

  return (
    <svg viewBox="0 0 100 100" className="w-full h-full">
      <rect x="0" y="0" width="100" height="100" fill="#0a0a0a" />
      {pts.map((d) => (
        <g key={d.drone_id}>
          <circle
            cx={px(d.position.longitude)}
            cy={py(d.position.latitude)}
            r="2.5"
            fill={HEALTH_COLORS[d.health] || "#6b7280"}
          />
          <text
            x={px(d.position.longitude) + 3}
            y={py(d.position.latitude) + 1}
            fontSize="3"
            fill="#94a3b8"
          >
            {d.drone_id}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default function ReplayPage() {
  const timeline = useReplayStore((s) => s.timeline);
  const currentFrameIndex = useReplayStore((s) => s.currentFrameIndex);
  const currentFrame = useReplayStore((s) => s.currentFrame);
  const playing = useReplayStore((s) => s.playing);
  const speed = useReplayStore((s) => s.speed);
  const play = useReplayStore((s) => s.play);
  const pause = useReplayStore((s) => s.pause);
  const setTimeline = useReplayStore((s) => s.setTimeline);
  const setFrameIndex = useReplayStore((s) => s.setFrameIndex);
  const setSpeed = useReplayStore((s) => s.setSpeed);
  const reset = useReplayStore((s) => s.reset);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const advanceRef = useRef(setFrameIndex);
  advanceRef.current = setFrameIndex;

  // Playback timer — advances frames at ~2 fps scaled by speed. Read-only.
  useEffect(() => {
    if (!playing || !timeline) return;
    const baseMs = 500;
    const interval = setInterval(() => {
      const { currentFrameIndex: idx, timeline: tl, pause: doPause } =
        useReplayStore.getState();
      if (!tl) return;
      if (idx >= tl.total_frames - 1) {
        doPause();
        return;
      }
      advanceRef.current(idx + 1);
    }, baseMs / speed);
    return () => clearInterval(interval);
  }, [playing, speed, timeline]);

  const loadTimeline = async () => {
    setError(null);
    setLoading(true);
    try {
      const tl = await getTwinRESTClient().startReplay();
      setTimeline(tl);
    } catch {
      setError("Failed to load replay timeline from the Digital Twin API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageShell
      title="Mission Replay"
      description="Historical mission reconstruction (read-only)"
    >
      {!timeline ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Play className="h-8 w-8 text-neutral-600 mx-auto mb-3" />
            <p className="text-sm text-neutral-500">No replay timeline loaded.</p>
            {isLiveMode() ? (
              <>
                <button
                  onClick={loadTimeline}
                  disabled={loading}
                  className="mt-3 inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
                >
                  {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                  Load recorded timeline
                </button>
                {error && (
                  <p className="text-xs text-red-400 mt-2">{error}</p>
                )}
              </>
            ) : (
              <p className="text-xs text-neutral-600 mt-1">
                Replay requires the Digital Twin API (set NEXT_PUBLIC_TWIN_API_URL).
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-neutral-300">
                Replay Viewer
              </h2>
              <div className="flex items-center gap-3 text-xs text-neutral-500 font-mono">
                <span>
                  {currentFrame ? fmtTime(currentFrame.timestamp_ms) : "--:--:--"}
                </span>
                <span>
                  Frame {currentFrameIndex + 1} / {timeline.total_frames}
                </span>
                <button
                  onClick={reset}
                  className="text-neutral-500 hover:text-neutral-300 underline"
                >
                  unload
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="h-64 border border-neutral-800 rounded-md overflow-hidden">
                <FrameScatter
                  drones={currentFrame?.swarm_state.drone_states ?? []}
                />
              </div>
              <div className="h-64 overflow-auto border border-neutral-800 rounded-md">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-neutral-900 text-neutral-500">
                    <tr>
                      <th className="text-left px-2 py-1.5">Drone</th>
                      <th className="text-left px-2 py-1.5">Battery</th>
                      <th className="text-left px-2 py-1.5">Health</th>
                      <th className="text-left px-2 py-1.5">Task</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(currentFrame?.swarm_state.drone_states ?? []).map((d) => (
                      <tr key={d.drone_id} className="border-t border-neutral-850">
                        <td className="px-2 py-1.5 text-neutral-300">
                          #{d.drone_id}
                        </td>
                        <td className="px-2 py-1.5 text-neutral-400 font-mono">
                          {Math.round(d.battery_pct)}%
                        </td>
                        <td className="px-2 py-1.5">
                          <span
                            className="inline-block h-2 w-2 rounded-full mr-1.5"
                            style={{
                              backgroundColor:
                                HEALTH_COLORS[d.health] || "#6b7280",
                            }}
                          />
                          <span className="text-neutral-400">{d.health}</span>
                        </td>
                        <td className="px-2 py-1.5 text-neutral-500">
                          {d.current_task}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-neutral-300">
                Playback Controls
              </h2>
              <span className="text-xs font-mono text-neutral-500">{speed}x</span>
            </div>

            <input
              type="range"
              min={0}
              max={Math.max(0, timeline.total_frames - 1)}
              value={currentFrameIndex}
              onChange={(e) => setFrameIndex(Number(e.target.value))}
              className="w-full mb-4 accent-blue-600"
            />

            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => setFrameIndex(0)}
                className="text-neutral-500 hover:text-neutral-300"
                title="First frame"
              >
                <SkipBack className="h-5 w-5" />
              </button>
              <button
                onClick={() => setSpeed(speed / 2)}
                className="text-neutral-500 hover:text-neutral-300"
                title="Slower"
              >
                <Rewind className="h-5 w-5" />
              </button>
              <button
                onClick={playing ? pause : play}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-white hover:bg-blue-500"
              >
                {playing ? (
                  <Pause className="h-5 w-5" />
                ) : (
                  <Play className="h-5 w-5 ml-0.5" />
                )}
              </button>
              <button
                onClick={() => setSpeed(speed * 2)}
                className="text-neutral-500 hover:text-neutral-300"
                title="Faster"
              >
                <FastForward className="h-5 w-5" />
              </button>
              <button
                onClick={() => setFrameIndex(timeline.total_frames - 1)}
                className="text-neutral-500 hover:text-neutral-300"
                title="Last frame"
              >
                <SkipForward className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}
