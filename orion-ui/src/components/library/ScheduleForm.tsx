"use client";

import { useCallback, useState } from "react";
import { Plus, X } from "lucide-react";
import {
  RECURRENCE_LABELS,
  type LibraryEntry,
  type Recurrence,
  type ScheduleInput,
} from "@/contracts/mission";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface ScheduleFormProps {
  /** Fixed saved mission, or a selector when a list of entries is supplied. */
  entryId?: string;
  entries?: readonly LibraryEntry[];
  busy: boolean;
  onSubmit: (input: ScheduleInput) => void;
  onCancel?: () => void;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Capture an operator's scheduling intent.
 *
 * Dates, times and the repeat rule are stored exactly as entered — the
 * scheduler never picks a better moment, rebalances or resolves conflicts.
 */
export function ScheduleForm({
  entryId,
  entries,
  busy,
  onSubmit,
  onCancel,
}: ScheduleFormProps) {
  const [selectedEntry, setSelectedEntry] = useState(
    entryId ?? entries?.[0]?.entry_id ?? ""
  );
  const [label, setLabel] = useState("");
  const [startDate, setStartDate] = useState(today());
  const [times, setTimes] = useState<string[]>(["06:00"]);
  const [recurrence, setRecurrence] = useState<Recurrence>("one_time");
  const [weekdays, setWeekdays] = useState<number[]>([]);
  const [intervalDays, setIntervalDays] = useState(2);

  const updateTime = useCallback((index: number, value: string) => {
    setTimes((prev) => prev.map((t, i) => (i === index ? value : t)));
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const entry = entryId ?? selectedEntry;
      if (!entry) return;
      onSubmit({
        entry_id: entry,
        label: label.trim(),
        start_date: startDate,
        times: times.filter(Boolean),
        recurrence,
        weekdays,
        interval_days: intervalDays,
        enabled: true,
      });
    },
    [
      entryId,
      selectedEntry,
      label,
      startDate,
      times,
      recurrence,
      weekdays,
      intervalDays,
      onSubmit,
    ]
  );

  const input =
    "w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600";

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-neutral-800 bg-neutral-900 p-4"
    >
      <h2 className="mb-1 text-sm font-medium text-neutral-300">
        Schedule this mission
      </h2>
      <p className="mb-3 text-[11px] text-neutral-500">
        The operator chooses the schedule. Times are stored as entered and the
        saved Mission Package is executed unchanged at each occurrence.
      </p>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {entries && !entryId && (
          <div>
            <label className="mb-1 block text-xs text-neutral-500" htmlFor="entry">
              Saved mission
            </label>
            <select
              id="entry"
              value={selectedEntry}
              onChange={(e) => setSelectedEntry(e.target.value)}
              className={input}
            >
              {entries.map((entry) => (
                <option key={entry.entry_id} value={entry.entry_id}>
                  {entry.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs text-neutral-500" htmlFor="label">
            Label
          </label>
          <input
            id="label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Morning passes"
            className={input}
          />
        </div>

        <div>
          <label className="mb-1 block text-xs text-neutral-500" htmlFor="date">
            Start date
          </label>
          <input
            id="date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className={input}
          />
        </div>

        <div>
          <label
            className="mb-1 block text-xs text-neutral-500"
            htmlFor="recurrence"
          >
            Repeat
          </label>
          <select
            id="recurrence"
            value={recurrence}
            onChange={(e) => setRecurrence(e.target.value as Recurrence)}
            className={input}
          >
            {(Object.keys(RECURRENCE_LABELS) as Recurrence[]).map((value) => (
              <option key={value} value={value}>
                {RECURRENCE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>

        {recurrence === "custom" && (
          <div>
            <label
              className="mb-1 block text-xs text-neutral-500"
              htmlFor="interval"
            >
              Every N days
            </label>
            <input
              id="interval"
              type="number"
              min={1}
              value={intervalDays}
              onChange={(e) => setIntervalDays(Number(e.target.value) || 1)}
              className={input}
            />
          </div>
        )}
      </div>

      {recurrence === "weekly" && (
        <div className="mt-3">
          <span className="mb-1 block text-xs text-neutral-500">Weekdays</span>
          <div className="flex flex-wrap gap-2">
            {WEEKDAYS.map((day, index) => {
              const active = weekdays.includes(index);
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() =>
                    setWeekdays((prev) =>
                      prev.includes(index)
                        ? prev.filter((d) => d !== index)
                        : [...prev, index].sort((a, b) => a - b)
                    )
                  }
                  className={`rounded-md border px-2 py-1 text-[11px] transition-colors ${
                    active
                      ? "border-blue-600 bg-blue-950/40 text-blue-300"
                      : "border-neutral-700 text-neutral-400 hover:bg-neutral-800"
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-3">
        <span className="mb-1 block text-xs text-neutral-500">
          Times (one or more per day)
        </span>
        <div className="flex flex-wrap items-center gap-2">
          {times.map((time, index) => (
            <div key={index} className="flex items-center gap-1">
              <input
                type="time"
                value={time}
                aria-label={`Time ${index + 1}`}
                onChange={(e) => updateTime(index, e.target.value)}
                className="rounded-md border border-neutral-700 bg-neutral-800 px-2 py-1.5 text-xs text-neutral-200 outline-none focus:border-blue-600"
              />
              {times.length > 1 && (
                <button
                  type="button"
                  aria-label={`Remove time ${index + 1}`}
                  onClick={() =>
                    setTimes((prev) => prev.filter((_, i) => i !== index))
                  }
                  className="rounded-md border border-neutral-700 p-1.5 text-neutral-500 hover:border-red-800 hover:text-red-400"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={() => setTimes((prev) => [...prev, "12:00"])}
            className="flex items-center gap-1 rounded-md border border-neutral-700 px-2 py-1.5 text-[11px] text-neutral-300 hover:bg-neutral-800"
          >
            <Plus className="h-3.5 w-3.5" /> Add time
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          type="submit"
          disabled={busy || times.length === 0}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Saving…" : "Create schedule"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-[11px] text-neutral-300 hover:bg-neutral-800"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
