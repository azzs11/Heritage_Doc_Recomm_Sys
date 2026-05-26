"use client";

import { useEffect } from "react";

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
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="text-5xl mb-4">⚠️</div>
        <h2 className="font-serif text-2xl font-bold text-heritage-dark mb-2">
          Something went wrong
        </h2>
        <p className="text-sm text-gray-500 mb-6">
          {error.message || "An unexpected error occurred. Please try again."}
        </p>
        <button
          onClick={reset}
          className="btn-primary"
          aria-label="Try again"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
