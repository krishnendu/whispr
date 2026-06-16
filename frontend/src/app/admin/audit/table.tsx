"use client";

import Link from "next/link";
import { useState } from "react";

import { api, type AuditEntry } from "@/lib/api";

const ACTION_FILTERS = [
  { value: "", label: "All" },
  { value: "honeypot_tag_attached", label: "Honeypot" },
  { value: "shadow_ban_toggled", label: "Ban toggle" },
  { value: "report_actioned", label: "Report actioned" },
  { value: "report_dismissed", label: "Report dismissed" },
];

const ACTION_STYLE: Record<string, string> = {
  honeypot_tag_attached: "border-[#E2624A]/30 bg-[#E2624A]/10 text-[#E2624A]",
  shadow_ban_toggled: "border-[#1A1A1A]/20 bg-[#1A1A1A]/5 text-[#1A1A1A]/80",
  report_actioned: "border-[#E2624A]/30 bg-[#E2624A]/10 text-[#E2624A]",
  report_dismissed: "border-[#1A1A1A]/10 bg-white text-[#1A1A1A]/40",
};

export function AuditTable({
  token,
  initial,
}: {
  token: string;
  initial: AuditEntry[];
}) {
  const [entries, setEntries] = useState<AuditEntry[]>(initial);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function applyFilter(action: string) {
    setFilter(action);
    setError(null);
    try {
      const r = await api.adminAuditLog(token, action || undefined);
      setEntries(r.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load.");
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
          <Link href="/admin/reports" className="hover:text-[#E2624A]">
            reports
          </Link>
          <Link href="/admin/users" className="hover:text-[#E2624A]">
            users
          </Link>
          <span className="text-[#E2624A]">audit</span>
        </div>
      </header>

      <section className="mx-auto mt-10 w-full max-w-5xl">
        <h1 className="font-[family-name:var(--font-instrument-serif)] text-4xl">
          Audit log
        </h1>
        <p className="mt-2 text-sm text-[#1A1A1A]/60">
          {entries.length} entr{entries.length === 1 ? "y" : "ies"}.
        </p>

        <div className="mt-6 flex flex-wrap gap-2">
          {ACTION_FILTERS.map((f) => (
            <button
              key={f.value || "all"}
              onClick={() => applyFilter(f.value)}
              className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                filter === f.value
                  ? "border-[#E2624A] bg-[#E2624A] text-white"
                  : "border-[#1A1A1A]/15 bg-white text-[#1A1A1A]/70 hover:border-[#1A1A1A]/40"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p className="mt-4 text-sm text-[#E2624A]">{error}</p>}

        <div className="mt-8 flex flex-col gap-3">
          {entries.length === 0 && (
            <p className="rounded-2xl border border-[#1A1A1A]/10 bg-white p-6 text-sm text-[#1A1A1A]/50">
              Nothing in the log.
            </p>
          )}
          {entries.map((e) => (
            <div
              key={e.id}
              className="flex flex-col gap-2 rounded-2xl border border-[#1A1A1A]/10 bg-white p-5"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className="font-mono text-xs text-[#1A1A1A]/40">
                    #{e.id}
                  </span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs uppercase tracking-wider ${ACTION_STYLE[e.action] ?? "border-[#1A1A1A]/15 bg-white text-[#1A1A1A]/60"}`}
                  >
                    {e.action}
                  </span>
                  <span className="text-sm text-[#1A1A1A]/70">
                    {e.actor ? `@${e.actor}` : "—"}
                    {e.target_type && (
                      <>
                        {" → "}
                        <span className="text-[#1A1A1A]/50">
                          {e.target_type}#{e.target_id}
                        </span>
                      </>
                    )}
                  </span>
                </div>
                <span className="text-xs text-[#1A1A1A]/40">
                  {new Date(e.created_at).toLocaleString()}
                </span>
              </div>

              {Object.keys(e.payload).length > 0 && (
                <pre className="overflow-x-auto rounded-xl bg-[#FAF7F2] p-3 font-mono text-xs text-[#1A1A1A]/70">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
