import { Suspense } from "react";

import { MagicClient } from "./client";

export default function MagicLandingPage() {
  return (
    <Suspense
      fallback={
        <main className="flex flex-1 items-center justify-center px-6">
          <p className="text-sm text-[#1A1A1A]/60">Signing you in…</p>
        </main>
      }
    >
      <MagicClient />
    </Suspense>
  );
}
