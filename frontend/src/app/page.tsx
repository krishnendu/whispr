import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex max-w-2xl flex-col items-center gap-10 text-center">
        <span className="rounded-full border border-[#1A1A1A]/15 px-3 py-1 text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/60">
          Whispr · early access
        </span>

        <h1 className="font-[family-name:var(--font-instrument-serif)] text-6xl leading-[1.05] tracking-tight sm:text-7xl">
          Whisper into the void.
          <br />
          <span className="text-[#E2624A]">Someone always whispers back.</span>
        </h1>

        <p className="max-w-lg text-lg leading-relaxed text-[#1A1A1A]/70">
          Anonymous chat. Pick a vibe. Get matched with someone — sometimes a person, sometimes a persona —
          and let the conversation evaporate when you're done.
        </p>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href="/signin"
            className="rounded-full bg-[#1A1A1A] px-8 py-3 text-sm font-medium text-[#FAF7F2] transition-colors hover:bg-[#E2624A]"
          >
            Step inside
          </Link>
          <Link
            href="#how"
            className="rounded-full border border-[#1A1A1A]/15 px-8 py-3 text-sm font-medium text-[#1A1A1A] transition-colors hover:bg-[#1A1A1A]/5"
          >
            How it works
          </Link>
        </div>

        <p className="mt-12 text-xs text-[#1A1A1A]/40">
          No real names. No phone. Messages auto-evaporate.
        </p>
      </div>
    </main>
  );
}
