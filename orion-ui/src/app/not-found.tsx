import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-8 text-center">
      <div className="mb-4 text-neutral-600">
        <Compass className="h-10 w-10" />
      </div>
      <h1 className="text-lg font-semibold text-neutral-100">Page not found</h1>
      <p className="mt-1 max-w-md text-sm text-neutral-500">
        The view you requested does not exist in Mission Control.
      </p>
      <Link
        href="/control"
        className="mt-6 inline-flex items-center gap-2 rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm text-neutral-200 transition-colors hover:bg-neutral-700"
      >
        Return to Mission Control
      </Link>
    </div>
  );
}
