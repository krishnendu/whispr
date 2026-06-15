"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export function MagicClient() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Missing token.");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { token: authToken, user } = await api.magicVerify(token);
        const res = await fetch("/auth/finish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: authToken }),
        });
        if (!res.ok) throw new Error("Failed to set session.");
        if (cancelled) return;
        router.replace(user.onboarding_complete ? "/home" : "/onboarding");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Sign in failed.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  return (
    <main className="flex flex-1 items-center justify-center px-6">
      <div className="text-center">
        {error ? (
          <p className="text-sm text-[#E2624A]">{error}</p>
        ) : (
          <p className="text-sm text-[#1A1A1A]/60">Signing you in…</p>
        )}
      </div>
    </main>
  );
}
