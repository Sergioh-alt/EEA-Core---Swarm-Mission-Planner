"use client";

import { useState } from "react";
import { useMissionStore } from "@/stores/missionStore";
import { MissionStatus } from "@/contracts/types";
import { cn } from "@/lib/utils";
import { Play, Pause, Square, RotateCcw } from "lucide-react";

type IntentType = "START_MISSION" | "PAUSE" | "STOP" | "REPLAY";

interface IntentAction {
  type: IntentType;
  label: string;
  icon: React.ReactNode;
  color: string;
  disabledWhen: MissionStatus[];
}

const INTENT_ACTIONS: IntentAction[] = [
  {
    type: "START_MISSION",
    label: "Start",
    icon: <Play className="h-3.5 w-3.5" />,
    color: "bg-green-600 hover:bg-green-500 text-white",
    disabledWhen: [MissionStatus.RUNNING],
  },
  {
    type: "PAUSE",
    label: "Pause",
    icon: <Pause className="h-3.5 w-3.5" />,
    color: "bg-yellow-600 hover:bg-yellow-500 text-white",
    disabledWhen: [MissionStatus.IDLE, MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED],
  },
  {
    type: "STOP",
    label: "Stop",
    icon: <Square className="h-3.5 w-3.5" />,
    color: "bg-red-600 hover:bg-red-500 text-white",
    disabledWhen: [MissionStatus.IDLE, MissionStatus.COMPLETED, MissionStatus.FAILED],
  },
  {
    type: "REPLAY",
    label: "Replay",
    icon: <RotateCcw className="h-3.5 w-3.5" />,
    color: "bg-blue-600 hover:bg-blue-500 text-white",
    disabledWhen: [MissionStatus.RUNNING],
  },
];

export function IntentBar() {
  const status = useMissionStore((s) => s.status);
  const [pendingIntent, setPendingIntent] = useState<IntentType | null>(null);

  const submitIntent = async (intentType: IntentType) => {
    setPendingIntent(intentType);
    // Intent submission goes to /api/intents → backend → Hive
    // UI never executes logic, only submits intents
    try {
      await fetch("/api/intents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: intentType,
          timestamp_ms: Date.now(),
          source: "operator",
        }),
      });
    } catch {
      // Intent submission failed — in production, the
      // connection status would reflect this
    } finally {
      setPendingIntent(null);
    }
  };

  return (
    <div className="flex items-center gap-1.5 px-3 py-2 bg-neutral-900/80 border-t border-neutral-800">
      <span className="text-[10px] text-neutral-600 mr-2 uppercase tracking-wider">
        Intents
      </span>
      {INTENT_ACTIONS.map((action) => {
        const disabled = action.disabledWhen.includes(status);
        const isPending = pendingIntent === action.type;

        return (
          <button
            key={action.type}
            onClick={() => submitIntent(action.type)}
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
