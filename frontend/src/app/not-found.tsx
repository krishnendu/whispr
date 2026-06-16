import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex max-w-md flex-col items-center gap-6 text-center">
        <span className="text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
          404
        </span>
        <h1 className="font-[family-name:var(--font-instrument-serif)] text-5xl leading-[1.05]">
          No whispers here.
        </h1>
        <p className="text-sm text-[#1A1A1A]/60">
          The page you're after either ended its session or never existed.
        </p>
        <Link
          href="/"
          className="rounded-full bg-[#1A1A1A] px-6 py-2 text-sm text-[#FAF7F2] hover:bg-[#E2624A]"
        >
          Back to the void
        </Link>
      </div>
    </main>
  );
}
