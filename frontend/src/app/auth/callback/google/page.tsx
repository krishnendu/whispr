import { Suspense } from "react";

import { GoogleCallbackClient } from "./client";

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="flex flex-1 items-center justify-center px-6">
          <p className="text-sm text-[#1A1A1A]/60">Signing you in…</p>
        </main>
      }
    >
      <GoogleCallbackClient />
    </Suspense>
  );
}
