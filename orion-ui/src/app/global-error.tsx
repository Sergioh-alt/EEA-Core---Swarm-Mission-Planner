"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

export default function GlobalError({
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
    <html lang="en" className="dark">
      <body className="bg-neutral-950 text-neutral-100 antialiased">
        <div className="flex min-h-screen flex-col items-center justify-center p-8 text-center">
          <div className="mb-4 text-red-500">
            <AlertTriangle className="h-10 w-10" />
          </div>
          <h1 className="text-lg font-semibold">Application error</h1>
          <p className="mt-1 max-w-md text-sm text-neutral-500">
            A critical error occurred and Mission Control could not recover this
            view automatically. Reload the application to continue.
          </p>
          <button
            onClick={reset}
            className="mt-6 inline-flex items-center gap-2 rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm text-neutral-200 transition-colors hover:bg-neutral-700"
          >
            <RotateCw className="h-4 w-4" />
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
