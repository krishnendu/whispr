"use client";

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";

export default function SignInPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">(
    "idle",
  );
  const [devLink, setDevLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sendMagic(e: React.FormEvent) {
    e.preventDefault();
    setStatus("sending");
    setError(null);
    setDevLink(null);
    try {
      const r = await api.magicSend(email);
      setStatus("sent");
      if (r.dev_link) setDevLink(r.dev_link);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function startGoogle() {
    setError(null);
    try {
      const { url } = await api.googleStart();
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google not configured.");
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex w-full max-w-md flex-col gap-8">
        <Link
          href="/"
          className="text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50 hover:text-[#E2624A]"
        >
          ← whispr
        </Link>

        <h1 className="font-[family-name:var(--font-instrument-serif)] text-5xl leading-[1.1]">
          Step inside.
        </h1>
        <p className="text-[#1A1A1A]/60">
          No password. Just a link in your inbox, or Google one tap.
        </p>

        <button
          onClick={startGoogle}
          className="flex items-center justify-center gap-2 rounded-full border border-[#1A1A1A]/15 bg-white px-6 py-3 text-sm font-medium transition-colors hover:bg-[#1A1A1A]/5"
        >
          Continue with Google
        </button>

        <div className="flex items-center gap-3 text-xs text-[#1A1A1A]/40">
          <span className="h-px flex-1 bg-[#1A1A1A]/10" />
          or
          <span className="h-px flex-1 bg-[#1A1A1A]/10" />
        </div>

        <form onSubmit={sendMagic} className="flex flex-col gap-3">
          <label htmlFor="email" className="text-sm text-[#1A1A1A]/70">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@somewhere.com"
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-3 text-sm focus:border-[#E2624A] focus:outline-none"
          />
          <button
            type="submit"
            disabled={status === "sending"}
            className="rounded-full bg-[#1A1A1A] px-6 py-3 text-sm font-medium text-[#FAF7F2] transition-colors hover:bg-[#E2624A] disabled:opacity-50"
          >
            {status === "sending" ? "Sending…" : "Email me a link"}
          </button>
        </form>

        {status === "sent" && (
          <div className="rounded-2xl border border-[#1A1A1A]/10 bg-white p-4 text-sm">
            <p className="text-[#1A1A1A]/80">Check your inbox.</p>
            {devLink && (
              <p className="mt-2 text-xs text-[#1A1A1A]/50">
                Dev mode — no SMTP configured.{" "}
                <a href={devLink} className="text-[#E2624A] underline">
                  Click the link directly →
                </a>
              </p>
            )}
          </div>
        )}

        {error && (
          <p className="text-sm text-[#E2624A]">{error}</p>
        )}
      </div>
    </main>
  );
}
