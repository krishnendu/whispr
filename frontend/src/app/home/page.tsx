import Link from "next/link";

import { requireUser } from "@/lib/session";

export default async function HomePage() {
  const { user } = await requireUser();

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

      <section className="flex flex-1 flex-col items-center justify-center gap-10 text-center">
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
            href="/onboarding"
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-8 py-3 text-sm font-medium text-[#1A1A1A] transition-colors hover:bg-[#1A1A1A]/5"
          >
            Edit vibe
          </Link>
        </div>
      </section>
    </main>
  );
}

