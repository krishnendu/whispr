"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api, type ChatMessage, type ConversationPayload } from "@/lib/api";

export function ChatClient({
  token,
  initial,
}: {
  token: string;
  initial: ConversationPayload;
}) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>(initial.messages);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [ended, setEnded] = useState(!!initial.ended_at);
  const [error, setError] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [blocking, setBlocking] = useState(false);
  const [otherTyping, setOtherTyping] = useState(false);
  const [vaulted, setVaulted] = useState(initial.is_vaulted);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastIdRef = useRef<number>(
    initial.messages.length
      ? initial.messages[initial.messages.length - 1].id
      : 0,
  );
  const lastTypingSentRef = useRef<number>(0);
  const typingStartedAtRef = useRef<number | null>(null);
  const pasteCountRef = useRef<number>(0);

  async function blockOther() {
    setBlocking(true);
    try {
      await api.blockInConversation(token, initial.id);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not block.");
      setBlocking(false);
    }
  }

  // SSE stream — server pushes new messages as soon as they're visible.
  // Falls back to polling if EventSource is unavailable (some old browsers).
  useEffect(() => {
    if (ended) return;
    const id = initial.id;

    if (typeof EventSource === "undefined") {
      // Polling fallback
      const tick = setInterval(async () => {
        try {
          const r = await api.pollConversation(token, id, lastIdRef.current);
          if (r.messages.length) {
            lastIdRef.current = r.messages[r.messages.length - 1].id;
            setMessages((prev) => {
              const seen = new Set(prev.map((m) => m.id));
              return [...prev, ...r.messages.filter((m) => !seen.has(m.id))];
            });
          }
          if (r.ended) setEnded(true);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Lost connection.");
        }
      }, 1500);
      return () => clearInterval(tick);
    }

    const es = new EventSource(api.streamUrl(token, id, lastIdRef.current));

    es.addEventListener("message", (e) => {
      const msg = JSON.parse((e as MessageEvent).data) as ChatMessage;
      lastIdRef.current = Math.max(lastIdRef.current, msg.id);
      setMessages((prev) =>
        prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
      );
      // A new message arrived → other side is clearly not typing right now.
      setOtherTyping(false);
    });

    es.addEventListener("typing", (e) => {
      const { typing } = JSON.parse((e as MessageEvent).data) as { typing: boolean };
      setOtherTyping(typing);
    });

    es.addEventListener("end", () => {
      setEnded(true);
      es.close();
    });

    es.onerror = () => {
      // EventSource auto-reconnects with Last-Event-ID. If readyState is CLOSED,
      // give up and surface an error. Otherwise stay quiet — reconnect is in flight.
      if (es.readyState === EventSource.CLOSED) {
        setError("Lost connection. Refresh to retry.");
      }
    };

    return () => es.close();
  }, [token, initial.id, ended]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || sending || ended) return;
    setSending(true);
    setError(null);
    const startedAt = typingStartedAtRef.current;
    const signals = {
      typing_ms: startedAt ? Date.now() - startedAt : 0,
      paste_count: pasteCountRef.current,
      length: body.length,
    };
    try {
      const msg = await api.postMessage(token, initial.id, body, signals);
      lastIdRef.current = Math.max(lastIdRef.current, msg.id);
      setMessages((prev) =>
        prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
      );
      setDraft("");
      typingStartedAtRef.current = null;
      pasteCountRef.current = 0;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send.");
    } finally {
      setSending(false);
    }
  }

  async function end() {
    try {
      await api.endConversation(token, initial.id);
    } finally {
      router.replace("/home");
    }
  }

  async function reroll() {
    try {
      const r = await api.rerollConversation(token, initial.id);
      if (r.status === "matched" && r.conversation_id) {
        router.replace(`/chat/${r.conversation_id}`);
        return;
      }
    } catch {
      // fall through to the queue page
    }
    router.replace("/match");
  }

  async function toggleVault() {
    try {
      if (vaulted) {
        await api.unvault(token, initial.id);
        setVaulted(false);
      } else {
        await api.vault(token, initial.id);
        setVaulted(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not vault.");
    }
  }

  function handleDraftChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    if (!draft && value && typingStartedAtRef.current === null) {
      typingStartedAtRef.current = Date.now();
    }
    setDraft(value);
    // Send typing ping at most every 3s; gives a 5s server-side TTL of headroom.
    const now = Date.now();
    if (now - lastTypingSentRef.current > 3000 && !ended) {
      lastTypingSentRef.current = now;
      void api.signalTyping(token, initial.id).catch(() => {
        /* ignore */
      });
    }
  }

  function handlePaste() {
    pasteCountRef.current += 1;
  }

  return (
    <main className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-[#1A1A1A]/10 bg-[#FAF7F2]/80 px-6 py-4 backdrop-blur">
        <div className="flex items-center gap-3">
          <Link
            href="/home"
            className="text-sm text-[#1A1A1A]/50 hover:text-[#E2624A]"
          >
            ←
          </Link>
          <span className="font-[family-name:var(--font-instrument-serif)] text-2xl">
            @{initial.other_handle}
          </span>
          {initial.kind === "bot" && (
            <span className="rounded-full border border-[#E2624A]/30 bg-[#E2624A]/10 px-2 py-0.5 text-xs uppercase tracking-wider text-[#E2624A]">
              persona
            </span>
          )}
          {initial.kind === "human" && initial.other_verified && (
            <span
              title="Signed in with a verified email"
              className="rounded-full border border-[#1A1A1A]/15 bg-white px-2 py-0.5 text-xs uppercase tracking-wider text-[#1A1A1A]/60"
            >
              ✓ verified
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleVault}
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A]"
          >
            {vaulted ? "★ saved" : "☆ save"}
          </button>
          <button
            onClick={() => setReportOpen(true)}
            disabled={ended}
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A] disabled:opacity-50"
          >
            report
          </button>
          {initial.kind === "human" && (
            <button
              onClick={blockOther}
              disabled={ended || blocking}
              className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A] disabled:opacity-50"
            >
              {blocking ? "…" : "block"}
            </button>
          )}
          {initial.kind === "human" && (
            <button
              onClick={reroll}
              disabled={ended}
              className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A] disabled:opacity-50"
            >
              find next
            </button>
          )}
          <button
            onClick={end}
            disabled={ended}
            className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A] disabled:opacity-50"
          >
            {ended ? "ended" : "end chat"}
          </button>
        </div>
      </header>
      {reportOpen && (
        <ReportModal
          token={token}
          conversationId={initial.id}
          onClose={() => setReportOpen(false)}
        />
      )}

      <section className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto flex max-w-2xl flex-col gap-3">
          {messages.length === 0 && (
            <p className="text-center text-sm text-[#1A1A1A]/40">
              Say hi. The vibe is yours to set.
            </p>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.is_me ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] rounded-3xl px-4 py-2 text-sm leading-relaxed ${
                  m.is_me
                    ? "bg-[#1A1A1A] text-[#FAF7F2]"
                    : "border border-[#1A1A1A]/10 bg-white text-[#1A1A1A]"
                }`}
              >
                {m.body}
              </div>
            </div>
          ))}
          {otherTyping && !ended && (
            <div className="flex justify-start">
              <div className="flex items-center gap-1 rounded-3xl border border-[#1A1A1A]/10 bg-white px-4 py-2 text-[#1A1A1A]/50">
                <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-[#1A1A1A]/40 [animation-delay:-0.2s]" />
                <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-[#1A1A1A]/40 [animation-delay:-0.1s]" />
                <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-[#1A1A1A]/40" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </section>

      <form
        onSubmit={send}
        className="border-t border-[#1A1A1A]/10 bg-[#FAF7F2]/80 px-6 py-4 backdrop-blur"
      >
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <input
            value={draft}
            onChange={handleDraftChange}
            onPaste={handlePaste}
            placeholder={ended ? "Conversation ended." : "Whisper something…"}
            disabled={ended || sending}
            className="flex-1 rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-3 text-sm focus:border-[#E2624A] focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={ended || sending || !draft.trim()}
            className="rounded-full bg-[#1A1A1A] px-6 py-3 text-sm font-medium text-[#FAF7F2] transition-colors hover:bg-[#E2624A] disabled:opacity-40"
          >
            {sending ? "…" : "Send"}
          </button>
        </div>
        {error && (
          <p className="mx-auto mt-2 max-w-2xl text-xs text-[#E2624A]">
            {error}
          </p>
        )}
      </form>
    </main>
  );
}

const REASONS: { value: string; label: string }[] = [
  { value: "spam", label: "Spam" },
  { value: "harassment", label: "Harassment" },
  { value: "nsfw", label: "NSFW outside spice" },
  { value: "minor", label: "Suspected minor" },
  { value: "other", label: "Other" },
];

function ReportModal({
  token,
  conversationId,
  onClose,
}: {
  token: string;
  conversationId: number;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("harassment");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.fileReport(token, {
        conversation_id: conversationId,
        reason,
        note,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-3xl bg-[#FAF7F2] p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="font-[family-name:var(--font-instrument-serif)] text-2xl">
            Report
          </h2>
          <button
            onClick={onClose}
            className="text-sm text-[#1A1A1A]/40 hover:text-[#E2624A]"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {done ? (
          <div className="mt-6 flex flex-col gap-4">
            <p className="text-sm text-[#1A1A1A]/70">
              Thanks. A moderator will review this.
            </p>
            <button
              onClick={onClose}
              className="self-start rounded-full bg-[#1A1A1A] px-6 py-2 text-sm text-[#FAF7F2]"
            >
              Close
            </button>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.15em] text-[#1A1A1A]/50">
                Reason
              </label>
              <div className="flex flex-wrap gap-2">
                {REASONS.map((r) => (
                  <button
                    type="button"
                    key={r.value}
                    onClick={() => setReason(r.value)}
                    className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                      reason === r.value
                        ? "border-[#E2624A] bg-[#E2624A] text-white"
                        : "border-[#1A1A1A]/15 bg-white text-[#1A1A1A]/70 hover:border-[#1A1A1A]/40"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.15em] text-[#1A1A1A]/50">
                Note <span className="text-[#1A1A1A]/30">(optional)</span>
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                maxLength={1000}
                className="rounded-2xl border border-[#1A1A1A]/15 bg-white px-4 py-3 text-sm focus:border-[#E2624A] focus:outline-none"
              />
            </div>
            {error && <p className="text-sm text-[#E2624A]">{error}</p>}
            <div className="flex justify-end gap-2">
              <button
                onClick={onClose}
                className="rounded-full border border-[#1A1A1A]/15 bg-white px-4 py-2 text-sm text-[#1A1A1A]/70 hover:bg-[#1A1A1A]/5"
              >
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={busy}
                className="rounded-full bg-[#1A1A1A] px-4 py-2 text-sm text-[#FAF7F2] disabled:opacity-50"
              >
                {busy ? "Sending…" : "Send report"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
