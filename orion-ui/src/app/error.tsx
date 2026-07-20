"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-full flex-col items-center justify-center p-8 text-center">
      <div className="mb-4 text-red-500">
        <AlertTriangle className="h-10 w-10" />
      </div>
      <h1 className="text-lg font-semibold text-neutral-100">
        Something went wrong
      </h1>
      <p className="mt-1 max-w-md text-sm text-neutral-500">
        An unexpected error occurred while rendering this view. Live Digital
        Twin streaming is unaffected — you can retry or navigate elsewhere.
      </p>
      <button
        onClick={reset}
        className="mt-6 inline-flex items-center gap-2 rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm text-neutral-200 transition-colors hover:bg-neutral-700"
      >
        <RotateCw className="h-4 w-4" />
        Try again
      </button>
    </div>
  );
}
