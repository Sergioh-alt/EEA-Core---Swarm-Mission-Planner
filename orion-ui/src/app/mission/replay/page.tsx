"use client";

import { PageShell } from "@/components/common/PageShell";
import { useReplayStore } from "@/stores/replayStore";
import { Play, Pause, SkipBack, SkipForward, Rewind, FastForward } from "lucide-react";

export default function ReplayPage() {
  const timeline = useReplayStore((s) => s.timeline);
  const currentFrameIndex = useReplayStore((s) => s.currentFrameIndex);
  const playing = useReplayStore((s) => s.playing);
  const speed = useReplayStore((s) => s.speed);
  const play = useReplayStore((s) => s.play);
  const pause = useReplayStore((s) => s.pause);
  const setFrameIndex = useReplayStore((s) => s.setFrameIndex);
  const setSpeed = useReplayStore((s) => s.setSpeed);

  return (
    <PageShell title="Mission Replay" description="Replay past mission data">
      {!timeline ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Play className="h-8 w-8 text-neutral-600 mx-auto mb-3" />
            <p className="text-sm text-neutral-500">
              No replay timeline loaded.
            </p>
            <p className="text-xs text-neutral-600 mt-1">
              Select a snapshot range to begin replay.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <h2 className="text-sm font-medium text-neutral-300 mb-3">
              Replay Viewer
            </h2>
            <div className="flex items-center justify-center h-64 border border-dashed border-neutral-800 rounded-md text-neutral-600">
              <p className="text-sm">
                Frame {currentFrameIndex + 1} / {timeline.total_frames}
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-neutral-300">
                Playback Controls
              </h2>
              <span className="text-xs font-mono text-neutral-500">
                {speed}x
              </span>
            </div>

            <div className="relative h-2 w-full rounded-full bg-neutral-800 mb-4 cursor-pointer">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-blue-600"
                style={{
                  width: `${
                    (currentFrameIndex / Math.max(1, timeline.total_frames - 1)) *
                    100
                  }%`,
                }}
              />
            </div>

            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => setFrameIndex(0)}
                className="text-neutral-500 hover:text-neutral-300"
              >
                <SkipBack className="h-5 w-5" />
              </button>
              <button
                onClick={() => setSpeed(speed / 2)}
                className="text-neutral-500 hover:text-neutral-300"
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
              >
                <FastForward className="h-5 w-5" />
              </button>
              <button
                onClick={() =>
                  setFrameIndex(timeline.total_frames - 1)
                }
                className="text-neutral-500 hover:text-neutral-300"
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
