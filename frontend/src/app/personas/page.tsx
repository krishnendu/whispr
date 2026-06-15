import Link from "next/link";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { PersonaCardButton } from "./card";

export default async function PersonasPage() {
  const { token } = await requireUser();
  const { personas } = await api.listPersonas(token);

  return (
    <main className="flex flex-1 flex-col px-6 py-12">
      <header className="flex w-full max-w-3xl items-center justify-between self-center">
        <Link
          href="/home"
          className="font-[family-name:var(--font-instrument-serif)] text-2xl"
        >
          ← whispr
        </Link>
        <span className="text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
          personas
        </span>
      </header>

      <section className="mx-auto mt-12 flex w-full max-w-3xl flex-col gap-8">
        <div className="flex flex-col gap-3">
          <h1 className="font-[family-name:var(--font-instrument-serif)] text-5xl leading-[1.05]">
            A cast of voices.
          </h1>
          <p className="text-[#1A1A1A]/60">
            Each persona has their own vibe. Pick someone and start whispering.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {personas.map((p) => (
            <PersonaCardButton key={p.slug} persona={p} token={token} />
          ))}
        </div>
      </section>
    </main>
  );
}
