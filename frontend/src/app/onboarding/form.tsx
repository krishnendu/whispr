"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, type TagsByCategory, type WhisprUser } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  mood: "Mood",
  topic: "Topic",
  spice: "Spice",
  language: "Language",
  region: "Region",
  time: "Time of day",
  custom: "Custom",
};

const CATEGORY_ORDER = ["mood", "topic", "time", "spice", "language", "region"];

export function OnboardingForm({
  token,
  user,
  tags,
}: {
  token: string;
  user: WhisprUser;
  tags: TagsByCategory;
}) {
  const router = useRouter();
  const [handle, setHandle] = useState(user.handle ?? "");
  const [ageConfirmed, setAgeConfirmed] = useState(user.age_confirmed);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(user.tags.map((t) => t.slug)),
  );
  const [pronouns, setPronouns] = useState(user.pronouns ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function toggle(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
      } else if (next.size < 8) {
        next.add(slug);
      }
      return next;
    });
  }

  const canSubmit =
    handle.trim().length >= 3 && ageConfirmed && selected.size >= 3 && !saving;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.updateMe(token, {
        handle: handle.trim().toLowerCase(),
        age_confirmed: ageConfirmed,
        pronouns: pronouns.trim(),
        tag_slugs: [...selected],
      });
      router.push("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center px-6 py-16">
      <form
        onSubmit={submit}
        className="flex w-full max-w-2xl flex-col gap-10"
      >
        <header className="flex flex-col gap-2">
          <span className="text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
            Step 1 of 1
          </span>
          <h1 className="font-[family-name:var(--font-instrument-serif)] text-5xl leading-[1.05]">
            Set your vibe.
          </h1>
          <p className="text-[#1A1A1A]/60">
            Pick a handle and 3–8 tags. We&apos;ll find people on a similar
            wavelength.
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <label htmlFor="handle" className="text-sm text-[#1A1A1A]/70">
            Handle
          </label>
          <input
            id="handle"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="silent-moth"
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-3 text-sm focus:border-[#E2624A] focus:outline-none"
          />
          <p className="text-xs text-[#1A1A1A]/40">
            3–32 chars, lowercase letters, numbers, dashes. We pre-filled a
            random one.
          </p>
        </section>

        <section className="flex flex-col gap-3">
          <label htmlFor="pronouns" className="text-sm text-[#1A1A1A]/70">
            Pronouns <span className="text-[#1A1A1A]/40">(optional)</span>
          </label>
          <input
            id="pronouns"
            value={pronouns}
            onChange={(e) => setPronouns(e.target.value)}
            placeholder="they/them"
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-3 text-sm focus:border-[#E2624A] focus:outline-none"
          />
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex items-baseline justify-between">
            <label className="text-sm text-[#1A1A1A]/70">
              Tags <span className="text-[#1A1A1A]/40">({selected.size}/8)</span>
            </label>
            <span className="text-xs text-[#1A1A1A]/40">Pick at least 3</span>
          </div>
          {CATEGORY_ORDER.filter((c) => tags.categories[c]).map((c) => (
            <div key={c} className="flex flex-col gap-2">
              <h3 className="text-xs uppercase tracking-[0.15em] text-[#1A1A1A]/40">
                {CATEGORY_LABELS[c] ?? c}
              </h3>
              <div className="flex flex-wrap gap-2">
                {tags.categories[c].map((t) => {
                  const active = selected.has(t.slug);
                  return (
                    <button
                      type="button"
                      key={t.slug}
                      onClick={() => toggle(t.slug)}
                      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                        active
                          ? "border-[#E2624A] bg-[#E2624A] text-white"
                          : "border-[#1A1A1A]/15 bg-white text-[#1A1A1A]/70 hover:border-[#1A1A1A]/40"
                      }`}
                    >
                      #{t.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </section>

        <section className="flex items-start gap-3 rounded-2xl border border-[#1A1A1A]/10 bg-white p-4">
          <input
            id="age"
            type="checkbox"
            checked={ageConfirmed}
            onChange={(e) => setAgeConfirmed(e.target.checked)}
            className="mt-1 h-4 w-4 accent-[#E2624A]"
          />
          <label htmlFor="age" className="text-sm text-[#1A1A1A]/70">
            I&apos;m 18 or older.{" "}
            <span className="text-[#1A1A1A]/40">
              Required to use Whispr. Spicy tags require this too.
            </span>
          </label>
        </section>

        {error && <p className="text-sm text-[#E2624A]">{error}</p>}

        <button
          type="submit"
          disabled={!canSubmit}
          className="self-start rounded-full bg-[#1A1A1A] px-8 py-3 text-sm font-medium text-[#FAF7F2] transition-colors hover:bg-[#E2624A] disabled:opacity-40"
        >
          {saving ? "Saving…" : "Step inside"}
        </button>
      </form>
    </main>
  );
}
