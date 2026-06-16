"use client";

import Link from "next/link";
import { useState } from "react";

import { api, type AdminReport } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  open: "border-[#E2624A]/30 bg-[#E2624A]/10 text-[#E2624A]",
  actioned: "border-[#1A1A1A]/15 bg-[#1A1A1A]/5 text-[#1A1A1A]/60",
  dismissed: "border-[#1A1A1A]/10 bg-white text-[#1A1A1A]/40",
};

export function ReportsTable({
  token,
  initial,
}: {
  token: string;
  initial: AdminReport[];
}) {
  const [reports, setReports] = useState<AdminReport[]>(initial);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: number, kind: "dismiss" | "action") {
    setBusy(id);
    setError(null);
    try {
      if (kind === "dismiss") await api.adminDismissReport(token, id);
      else await api.adminActionReport(token, id);
      setReports((prev) =>
        prev.map((r) =>
          r.id === id ? { ...r, status: kind === "dismiss" ? "dismissed" : "actioned" } : r,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="flex flex-1 flex-col px-6 py-12">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between">
        <Link
          href="/home"
          className="font-[family-name:var(--font-instrument-serif)] text-2xl"
        >
          ← whispr
        </Link>
        <div className="flex items-center gap-4 text-xs uppercase tracking-[0.2em] text-[#1A1A1A]/50">
          <span className="text-[#E2624A]">reports</span>
          <Link href="/admin/users" className="hover:text-[#E2624A]">
            users
          </Link>
          <Link href="/admin/audit" className="hover:text-[#E2624A]">
            audit
          </Link>
        </div>
      </header>

      <section className="mx-auto mt-10 w-full max-w-5xl">
        <h1 className="font-[family-name:var(--font-instrument-serif)] text-4xl">
          Moderation queue
        </h1>
        <p className="mt-2 text-sm text-[#1A1A1A]/60">
          {reports.length} report{reports.length === 1 ? "" : "s"}.
        </p>

        {error && <p className="mt-4 text-sm text-[#E2624A]">{error}</p>}

        <div className="mt-8 flex flex-col gap-3">
          {reports.length === 0 && (
            <p className="rounded-2xl border border-[#1A1A1A]/10 bg-white p-6 text-sm text-[#1A1A1A]/50">
              Nothing in the queue.
            </p>
          )}
          {reports.map((r) => (
            <div
              key={r.id}
              className="flex flex-col gap-3 rounded-2xl border border-[#1A1A1A]/10 bg-white p-5"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-xs text-[#1A1A1A]/40">
                    #{r.id}
                  </span>
                  <span className="text-sm font-medium">
                    @{r.reporter ?? "—"} → @{r.target ?? "persona"}
                  </span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs uppercase tracking-wider ${STATUS_STYLE[r.status] ?? ""}`}
                  >
                    {r.status}
                  </span>
                </div>
                <span className="text-xs text-[#1A1A1A]/40">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full border border-[#1A1A1A]/15 px-2 py-0.5 text-xs uppercase tracking-wider text-[#1A1A1A]/60">
                  {r.reason}
                </span>
                {r.conversation_id && (
                  <span className="text-xs text-[#1A1A1A]/40">
                    convo #{r.conversation_id}
                  </span>
                )}
              </div>

              {r.note && (
                <p className="rounded-xl bg-[#FAF7F2] p-3 text-sm text-[#1A1A1A]/70">
                  “{r.note}”
                </p>
              )}

              {r.status === "open" && (
                <div className="flex gap-2">
                  <button
                    onClick={() => act(r.id, "dismiss")}
                    disabled={busy === r.id}
                    className="rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-1.5 text-xs text-[#1A1A1A]/60 hover:bg-[#1A1A1A]/5 disabled:opacity-50"
                  >
                    Dismiss
                  </button>
                  <button
                    onClick={() => act(r.id, "action")}
                    disabled={busy === r.id || !r.target_id}
                    className="rounded-full bg-[#1A1A1A] px-4 py-1.5 text-xs text-[#FAF7F2] hover:bg-[#E2624A] disabled:opacity-40"
                  >
                    Shadow-ban target
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
