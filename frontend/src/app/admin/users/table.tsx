"use client";

import Link from "next/link";
import { useState } from "react";

import { api, type AdminUser } from "@/lib/api";

export function UsersTable({
  token,
  initial,
}: {
  token: string;
  initial: AdminUser[];
}) {
  const [users, setUsers] = useState<AdminUser[]>(initial);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const r = await api.adminUsers(token, q.trim() || undefined);
      setUsers(r.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    }
  }

  async function toggleBan(id: number) {
    setBusy(id);
    setError(null);
    try {
      const r = await api.adminToggleBan(token, id);
      setUsers((prev) =>
        prev.map((u) =>
          u.id === id ? { ...u, is_shadow_banned: r.is_shadow_banned } : u,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed.");
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
          <Link href="/admin/reports" className="hover:text-[#E2624A]">
            reports
          </Link>
          <span className="text-[#E2624A]">users</span>
          <Link href="/admin/audit" className="hover:text-[#E2624A]">
            audit
          </Link>
        </div>
      </header>

      <section className="mx-auto mt-10 w-full max-w-5xl">
        <h1 className="font-[family-name:var(--font-instrument-serif)] text-4xl">
          Users
        </h1>

        <form onSubmit={search} className="mt-6 flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="search handle…"
            className="flex-1 rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-2 text-sm focus:border-[#E2624A] focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-full bg-[#1A1A1A] px-4 py-2 text-sm text-[#FAF7F2] hover:bg-[#E2624A]"
          >
            Search
          </button>
        </form>

        {error && <p className="mt-3 text-sm text-[#E2624A]">{error}</p>}

        <div className="mt-6 overflow-hidden rounded-2xl border border-[#1A1A1A]/10 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#FAF7F2] text-left text-xs uppercase tracking-wider text-[#1A1A1A]/40">
              <tr>
                <th className="px-4 py-3">Handle</th>
                <th className="px-4 py-3">Trust</th>
                <th className="px-4 py-3">Verified</th>
                <th className="px-4 py-3">Joined</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1A1A1A]/5">
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-[#1A1A1A]/40">
                    No users.
                  </td>
                </tr>
              )}
              {users.map((u) => (
                <tr key={u.id} className={u.is_shadow_banned ? "opacity-50" : ""}>
                  <td className="px-4 py-3">
                    @{u.handle}
                    {u.is_shadow_banned && (
                      <span className="ml-2 rounded-full border border-[#E2624A]/30 bg-[#E2624A]/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-[#E2624A]">
                        banned
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{u.trust_score}</td>
                  <td className="px-4 py-3">
                    {u.is_verified ? "✓" : "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-[#1A1A1A]/40">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => toggleBan(u.id)}
                      disabled={busy === u.id}
                      className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 hover:text-[#E2624A] disabled:opacity-50"
                    >
                      {u.is_shadow_banned ? "unban" : "shadow-ban"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
