"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api, type ChatMessage, type ConversationPayload } from "@/lib/api";

const POLL_MS = 1500;

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
  const bottomRef = useRef<HTMLDivElement>(null);
  const endedRef = useRef(ended);
  const lastIdRef = useRef<number>(
    initial.messages.length
      ? initial.messages[initial.messages.length - 1].id
      : 0,
  );

  useEffect(() => {
    endedRef.current = ended;
  }, [ended]);

  // Poll for new messages from the other side. Stable identity → set up once.
  useEffect(() => {
    let cancelled = false;
    const id = initial.id;
    const tick = setInterval(async () => {
      if (endedRef.current || cancelled) return;
      try {
        const r = await api.pollConversation(token, id, lastIdRef.current);
        if (cancelled) return;
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
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(tick);
    };
  }, [token, initial.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = draft.trim();
    if (!body || sending || ended) return;
    setSending(true);
    setError(null);
    try {
      const msg = await api.postMessage(token, initial.id, body);
      lastIdRef.current = Math.max(lastIdRef.current, msg.id);
      setMessages((prev) =>
        prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
      );
      setDraft("");
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
        </div>
        <button
          onClick={end}
          disabled={ended}
          className="rounded-full border border-[#1A1A1A]/15 bg-white px-3 py-1 text-xs text-[#1A1A1A]/60 transition-colors hover:text-[#E2624A] disabled:opacity-50"
        >
          {ended ? "ended" : "end chat"}
        </button>
      </header>

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
            onChange={(e) => setDraft(e.target.value)}
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
