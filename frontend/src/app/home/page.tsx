import Link from "next/link";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

export default async function HomePage() {
  const { token, user } = await requireUser();
  const { items: vault } = await api.myVault(token).catch(() => ({ items: [] }));

  return (
    <main className="flex flex-1 flex-col px-6 py-12">
      <header className="flex w-full max-w-3xl items-center justify-between self-center">
        <Link
          href="/"
          className="font-[family-name:var(--font-instrument-serif)] text-2xl"
        >
          whispr
        </Link>
        <div className="flex items-center gap-4 text-sm text-[#1A1A1A]/60">
          {user.is_operator && (
            <Link
              href="/admin/reports"
              className="text-xs uppercase tracking-[0.15em] text-[#E2624A] hover:underline"
            >
              admin
            </Link>
          )}
          <span>@{user.handle}</span>
          <form action="/auth/signout" method="post">
            <button
              type="submit"
              className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 hover:text-[#E2624A]"
            >
              sign out
            </button>
          </form>
        </div>
      </header>

      <section className="mx-auto mt-16 flex w-full max-w-3xl flex-col items-center gap-10 text-center">
        <span className="rounded-full border border-[#1A1A1A]/15 px-3 py-1 text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/60">
          {user.tags.length} tags · trust {user.trust_score}
        </span>

        <h1 className="font-[family-name:var(--font-instrument-serif)] text-6xl leading-[1.05]">
          Whose voice <br />
          do you want tonight?
        </h1>

        <div className="flex flex-wrap justify-center gap-2 text-sm text-[#1A1A1A]/60">
          {user.tags.map((t) => (
            <span
              key={t.slug}
              className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1"
            >
              #{t.label}
            </span>
          ))}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href="/match"
            className="rounded-full bg-[#1A1A1A] px-8 py-3 text-sm font-medium text-[#FAF7F2] transition-colors hover:bg-[#E2624A]"
          >
            Find someone
          </Link>
          <Link
            href="/personas"
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-8 py-3 text-sm font-medium text-[#1A1A1A] transition-colors hover:bg-[#1A1A1A]/5"
          >
            Browse personas
          </Link>
          <Link
            href="/onboarding"
            className="rounded-full border border-transparent px-6 py-3 text-sm text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A]"
          >
            Edit vibe
          </Link>
        </div>
      </section>

      {vault.length > 0 && (
        <section className="mx-auto mt-20 flex w-full max-w-3xl flex-col gap-4">
          <h2 className="text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
            Saved · {vault.length}/10
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {vault.map((v) => (
              <Link
                key={v.id}
                href={`/chat/${v.id}`}
                className="flex flex-col gap-2 rounded-2xl border border-[#1A1A1A]/10 bg-white p-4 transition-colors hover:border-[#E2624A]"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-[family-name:var(--font-instrument-serif)] text-xl">
                    @{v.other_handle}
                  </span>
                  {v.kind === "bot" && (
                    <span className="rounded-full border border-[#E2624A]/30 bg-[#E2624A]/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-[#E2624A]">
                      persona
                    </span>
                  )}
                </div>
                <p className="text-sm text-[#1A1A1A]/60 line-clamp-2">
                  {v.summary_text || (v.ended_at ? "Conversation ended." : "Still open.")}
                </p>
                <span className="text-[10px] uppercase tracking-wider text-[#1A1A1A]/40">
                  {new Date(v.started_at).toLocaleDateString()}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
