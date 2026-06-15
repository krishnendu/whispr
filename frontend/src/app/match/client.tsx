"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type WhisprUser } from "@/lib/api";

export function MatchClient({
  token,
  tags,
}: {
  token: string;
  tags: WhisprUser["tags"];
}) {
  const router = useRouter();
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        const s = await api.matchStatus(token);
        if (cancelled) return;
        if (s.status === "matched" && s.conversation_id) {
          router.replace(`/chat/${s.conversation_id}`);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Lost connection.");
        }
      }
    }

    (async () => {
      try {
        const r = await api.matchStart(token);
        if (cancelled) return;
        if (r.status === "matched" && r.conversation_id) {
          router.replace(`/chat/${r.conversation_id}`);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not start.");
        }
      }
    })();

    const id = setInterval(tick, 1500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [token, router]);

  useEffect(() => {
    const tickClock = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(tickClock);
  }, []);

  async function cancel() {
    try {
      await api.matchCancel(token);
    } finally {
      router.replace("/home");
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex max-w-lg flex-col items-center gap-8 text-center">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#E2624A] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[#E2624A]" />
          </span>
          listening for whispers
        </div>

        <h1 className="font-[family-name:var(--font-instrument-serif)] text-5xl leading-[1.05]">
          Looking for someone <br /> on your wavelength.
        </h1>

        <div className="flex flex-wrap justify-center gap-2 text-sm text-[#1A1A1A]/60">
          {tags.map((t) => (
            <span
              key={t.slug}
              className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1"
            >
              #{t.label}
            </span>
          ))}
        </div>

        <p className="text-sm text-[#1A1A1A]/50 tabular-nums">
          {seconds}s elapsed
        </p>

        {error && <p className="text-sm text-[#E2624A]">{error}</p>}

        <button
          onClick={cancel}
          className="rounded-full border border-[#1A1A1A]/15 bg-white px-6 py-2 text-sm text-[#1A1A1A]/70 transition-colors hover:bg-[#1A1A1A]/5"
        >
          Cancel
        </button>
      </div>
    </main>
  );
}
