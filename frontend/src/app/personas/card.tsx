"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, type PersonaCard } from "@/lib/api";

export function PersonaCardButton({
  persona,
  token,
}: {
  persona: PersonaCard;
  token: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const interests = persona.persona_card.interests ?? [];
  const ageVibe = persona.persona_card.age_vibe;

  async function open() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.startPersonaChat(token, persona.slug);
      router.push(`/chat/${r.conversation_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open chat.");
      setBusy(false);
    }
  }

  return (
    <button
      onClick={open}
      disabled={busy}
      className="group flex flex-col items-start gap-3 rounded-3xl border border-[#1A1A1A]/10 bg-white p-6 text-left transition-colors hover:border-[#E2624A] disabled:opacity-50"
    >
      <div className="flex w-full items-baseline justify-between">
        <span className="font-[family-name:var(--font-instrument-serif)] text-3xl">
          {persona.name}
        </span>
        {persona.spice_level !== "sfw" && (
          <span className="rounded-full border border-[#E2624A]/30 bg-[#E2624A]/10 px-2 py-0.5 text-xs uppercase tracking-wider text-[#E2624A]">
            {persona.spice_level}
          </span>
        )}
      </div>
      {ageVibe && (
        <p className="text-xs uppercase tracking-[0.15em] text-[#1A1A1A]/40">
          {ageVibe}
        </p>
      )}
      {interests.length > 0 && (
        <p className="text-sm text-[#1A1A1A]/60">
          into {interests.slice(0, 3).join(", ")}
        </p>
      )}
      <span className="mt-2 text-xs text-[#1A1A1A]/40 group-hover:text-[#E2624A]">
        {busy ? "opening…" : "whisper →"}
      </span>
      {error && <p className="text-xs text-[#E2624A]">{error}</p>}
    </button>
  );
}
