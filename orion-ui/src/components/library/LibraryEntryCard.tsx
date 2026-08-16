"use client";

import Link from "next/link";
import { Archive, Copy, Trash2 } from "lucide-react";
import type { LibraryEntry } from "@/contracts/mission";

interface LibraryEntryCardProps {
  entry: LibraryEntry;
  busy: boolean;
  onDuplicate: (entry: LibraryEntry) => void;
  onArchive: (entry: LibraryEntry) => void;
  onDelete: (entry: LibraryEntry) => void;
}

function formatUpdated(ms: number): string {
  return new Date(ms).toLocaleString();
}

/** One saved mission. All figures are backend values, never recomputed here. */
export function LibraryEntryCard({
  entry,
  busy,
  onDuplicate,
  onArchive,
  onDelete,
}: LibraryEntryCardProps) {
  const s = entry.summary;
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <div className="flex items-start justify-between gap-3">
        <Link href={`/library/${entry.entry_id}`} className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-neutral-100">
              {entry.name}
            </span>
            {entry.template && (
              <span className="rounded border border-blue-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-blue-300">
                Template
              </span>
            )}
            {entry.status === "archived" && (
              <span className="rounded border border-neutral-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-neutral-400">
                Archived
              </span>
            )}
            {entry.package_stale && (
              <span className="rounded border border-amber-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-amber-300">
                Package outdated
              </span>
            )}
            {!entry.package && (
              <span className="rounded border border-amber-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-amber-300">
                No package
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-neutral-500">
            <span>{s.field_name || "—"}</span>
            <span>{s.operation_type || "—"}</span>
            <span>{s.fleet_count} drones</span>
            <span>{s.products.length} products</span>
            {s.area_ha !== null && <span>{s.area_ha.toFixed(2)} ha</span>}
            {s.route_count !== null && <span>{s.route_count} routes</span>}
            {s.go_no_go && <span>{s.go_no_go}</span>}
            {s.estimated_duration && <span>{s.estimated_duration}</span>}
          </div>
          <p className="mt-1 text-[10px] text-neutral-600">
            v{entry.version} · updated {formatUpdated(entry.updated_ms)}
          </p>
        </Link>

        <div className="flex shrink-0 items-center gap-2">
          <Link
            href={`/library/${entry.entry_id}`}
            className="rounded-md border border-neutral-700 px-2 py-1 text-[11px] text-blue-400 transition-colors hover:bg-neutral-800"
          >
            Open
          </Link>
          <button
            type="button"
            disabled={busy}
            onClick={() => onDuplicate(entry)}
            aria-label={`Duplicate ${entry.name}`}
            className="rounded-md border border-neutral-700 p-2 text-neutral-400 transition-colors hover:bg-neutral-800 disabled:opacity-50"
          >
            <Copy className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onArchive(entry)}
            aria-label={
              entry.status === "archived"
                ? `Restore ${entry.name}`
                : `Archive ${entry.name}`
            }
            className="rounded-md border border-neutral-700 p-2 text-neutral-400 transition-colors hover:bg-neutral-800 disabled:opacity-50"
          >
            <Archive className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onDelete(entry)}
            aria-label={`Remove ${entry.name}`}
            className="rounded-md border border-neutral-700 p-2 text-neutral-500 transition-colors hover:border-red-800 hover:text-red-400 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
