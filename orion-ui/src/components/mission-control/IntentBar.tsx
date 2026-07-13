"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMissionStore } from "@/stores/missionStore";
import { MissionStatus } from "@/contracts/types";
import type { IntentType } from "@/contracts/intents";
import { getTwinRESTClient } from "@/lib/restClient";
import { cn } from "@/lib/utils";
import { Play, Pause, Square, RotateCcw } from "lucide-react";

interface IntentAction {
  key: string;
  label: string;
  icon: React.ReactNode;
  color: string;
  disabledWhen: MissionStatus[];
}

const INTENT_ACTIONS: IntentAction[] = [
  {
    key: "start",
    label: "Start",
    icon: <Play className="h-3.5 w-3.5" />,
    color: "bg-green-600 hover:bg-green-500 text-white",
    disabledWhen: [MissionStatus.RUNNING],
  },
  {
    key: "pause",
    label: "Pause",
    icon: <Pause className="h-3.5 w-3.5" />,
    color: "bg-yellow-600 hover:bg-yellow-500 text-white",
    disabledWhen: [MissionStatus.IDLE, MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED],
  },
  {
    key: "stop",
    label: "Stop",
    icon: <Square className="h-3.5 w-3.5" />,
    color: "bg-red-600 hover:bg-red-500 text-white",
    disabledWhen: [MissionStatus.IDLE, MissionStatus.COMPLETED, MissionStatus.FAILED],
  },
  {
    key: "replay",
    label: "Replay",
    icon: <RotateCcw className="h-3.5 w-3.5" />,
    color: "bg-blue-600 hover:bg-blue-500 text-white",
    disabledWhen: [MissionStatus.RUNNING],
  },
];

export function IntentBar() {
  const status = useMissionStore((s) => s.status);
  const router = useRouter();
  const [pending, setPending] = useState<string | null>(null);

  // The UI only submits an intent — the backend (Hive) accepts or rejects.
  const submit = async (intentType: IntentType) => {
    try {
      await getTwinRESTClient().submitIntent({
        intent_type: intentType,
        payload: {},
        user_id: "operator",
        timestamp_ms: Date.now(),
      });
    } catch {
      // Rejected / unreachable — connection status reflects transport health.
    }
  };

  const onAction = async (key: string) => {
    setPending(key);
    try {
      if (key === "replay") {
        router.push("/mission/replay");
        return;
      }
      if (key === "start") {
        await submit(
          status === MissionStatus.PAUSED ? "RESUME_MISSION" : "START_MISSION"
        );
      } else if (key === "pause") {
        await submit("PAUSE_MISSION");
      } else if (key === "stop") {
        await submit("STOP_MISSION");
      }
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="flex items-center gap-1.5 px-3 py-2 bg-neutral-900/80 border-t border-neutral-800">
      <span className="text-[10px] text-neutral-600 mr-2 uppercase tracking-wider">
        Intents
      </span>
      {INTENT_ACTIONS.map((action) => {
        const disabled = action.disabledWhen.includes(status);
        const isPending = pending === action.key;

        return (
          <button
            key={action.key}
            onClick={() => onAction(action.key)}
            disabled={disabled || isPending}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[10px] font-medium transition-all",
              disabled || isPending
                ? "bg-neutral-800 text-neutral-600 cursor-not-allowed"
                : action.color
            )}
          >
            {action.icon}
            {isPending ? "..." : action.label}
          </button>
        );
      })}
    </div>
  );
}
