"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Could wire to a logger here.
    console.error(error);
  }, [error]);

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex max-w-md flex-col items-center gap-6 text-center">
        <span className="text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
          something went sideways
        </span>
        <h1 className="font-[family-name:var(--font-instrument-serif)] text-5xl leading-[1.05]">
          The void is unusually quiet.
        </h1>
        <p className="text-sm text-[#1A1A1A]/60">
          We hit an error rendering this screen. Try again — or head back home.
        </p>
        <div className="flex gap-3">
          <button
            onClick={reset}
            className="rounded-full bg-[#1A1A1A] px-6 py-2 text-sm text-[#FAF7F2] hover:bg-[#E2624A]"
          >
            Try again
          </button>
          <Link
            href="/home"
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-6 py-2 text-sm text-[#1A1A1A]/70 hover:bg-[#1A1A1A]/5"
          >
            Home
          </Link>
        </div>
      </div>
    </main>
  );
}
