/**
 * Thin Whispr API client. Reads `whispr_token` from cookies on the server (via
 * `cookies()`) or from a passed-in token on the client (via `useAuth`).
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type WhisprUser = {
  id: number;
  handle: string;
  pronouns: string;
  locale: string;
  age_confirmed: boolean;
  trust_score: number;
  is_operator: boolean;
  is_verified: boolean;
  onboarding_complete: boolean;
  tags: { slug: string; label: string; category: string }[];
};

export type TagsByCategory = {
  categories: Record<
    string,
    {
      slug: string;
      label: string;
      category: string;
      is_user_created: boolean;
      is_honeypot?: boolean;
      usage_count: number;
    }[]
  >;
};

async function req<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers, ...rest } = init;
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...(headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean }>("/api/health"),

  // Auth
  googleStart: () => req<{ url: string }>("/api/auth/google/start"),
  googleCallback: (code: string) =>
    req<{ token: string; user: WhisprUser }>("/api/auth/google/callback", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  magicSend: (email: string) =>
    req<{ sent: boolean; dev_link?: string }>("/api/auth/magic/send", {
      method: "POST",
      body: JSON.stringify({
        email,
        frontend_base:
          typeof window !== "undefined" ? window.location.origin : undefined,
      }),
    }),
  magicVerify: (token: string) =>
    req<{ token: string; user: WhisprUser }>("/api/auth/magic/verify", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  // Profile
  me: (token: string) => req<WhisprUser>("/api/me", { token }),
  updateMe: (
    token: string,
    body: Partial<{
      handle: string;
      pronouns: string;
      locale: string;
      age_confirmed: boolean;
      tag_slugs: string[];
    }>,
  ) =>
    req<WhisprUser>("/api/me", {
      method: "PUT",
      token,
      body: JSON.stringify(body),
    }),

  // Tags
  tags: (q?: string) =>
    req<TagsByCategory>(`/api/tags${q ? `?q=${encodeURIComponent(q)}` : ""}`),

  // Matching
  matchStart: (token: string) =>
    req<{ status: "matched" | "waiting"; conversation_id?: number }>(
      "/api/match/start",
      { method: "POST", token, body: "{}" },
    ),
  matchStatus: (token: string) =>
    req<{ status: "idle" | "waiting" | "matched"; conversation_id?: number }>(
      "/api/match/status",
      { token },
    ),
  matchCancel: (token: string) =>
    req<{ status: string }>("/api/match/cancel", {
      method: "POST",
      token,
      body: "{}",
    }),

  // Chat
  getConversation: (token: string, id: number) =>
    req<ConversationPayload>(`/api/conversations/${id}`, { token }),
  pollConversation: (token: string, id: number, afterId: number) =>
    req<{ messages: ChatMessage[]; ended: boolean }>(
      `/api/conversations/${id}/poll?after=${afterId}`,
      { token },
    ),
  streamUrl: (token: string, id: number, afterId: number) =>
    `${API_BASE}/api/conversations/${id}/stream?token=${encodeURIComponent(token)}&after=${afterId}`,
  postMessage: (
    token: string,
    id: number,
    body: string,
    signals?: { typing_ms?: number; paste_count?: number; length?: number },
  ) =>
    req<ChatMessage>(`/api/conversations/${id}/messages`, {
      method: "POST",
      token,
      body: JSON.stringify({ body, signals }),
    }),
  endConversation: (token: string, id: number) =>
    req<{ ended: boolean }>(`/api/conversations/${id}/end`, {
      method: "POST",
      token,
      body: "{}",
    }),
  rerollConversation: (token: string, id: number) =>
    req<{ status: "matched" | "waiting"; conversation_id?: number }>(
      `/api/conversations/${id}/reroll`,
      { method: "POST", token, body: "{}" },
    ),
  signalTyping: (token: string, id: number) =>
    req<{ ok: boolean }>(`/api/conversations/${id}/typing`, {
      method: "POST",
      token,
      body: "{}",
    }),
  vault: (token: string, id: number) =>
    req<{ vaulted: boolean }>(`/api/conversations/${id}/vault`, {
      method: "POST",
      token,
      body: "{}",
    }),
  unvault: (token: string, id: number) =>
    req<{ vaulted: boolean }>(`/api/conversations/${id}/unvault`, {
      method: "POST",
      token,
      body: "{}",
    }),
  myVault: (token: string) =>
    req<{ items: VaultItem[] }>("/api/me/vault", { token }),

  // Personas
  listPersonas: (token: string) =>
    req<{ personas: PersonaCard[] }>("/api/personas", { token }),
  startPersonaChat: (token: string, slug: string) =>
    req<{ conversation_id: number; persona: PersonaCard }>(
      `/api/personas/${slug}/start`,
      { method: "POST", token, body: "{}" },
    ),

  // Moderation
  fileReport: (
    token: string,
    body: { conversation_id?: number; reason: string; note?: string },
  ) =>
    req<{ filed: boolean }>("/api/report", {
      method: "POST",
      token,
      body: JSON.stringify(body),
    }),
  blockInConversation: (token: string, convoId: number) =>
    req<{ blocked: boolean }>(`/api/conversations/${convoId}/block`, {
      method: "POST",
      token,
      body: "{}",
    }),
  adminReports: (token: string) =>
    req<{ reports: AdminReport[] }>("/api/admin/reports", { token }),
  adminDismissReport: (token: string, id: number) =>
    req<{ ok: boolean }>(`/api/admin/reports/${id}/dismiss`, {
      method: "POST",
      token,
      body: "{}",
    }),
  adminActionReport: (token: string, id: number) =>
    req<{ ok: boolean }>(`/api/admin/reports/${id}/action`, {
      method: "POST",
      token,
      body: "{}",
    }),
  adminUsers: (token: string, q?: string) =>
    req<{ users: AdminUser[] }>(
      `/api/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`,
      { token },
    ),
  adminToggleBan: (token: string, id: number) =>
    req<{ is_shadow_banned: boolean }>(
      `/api/admin/users/${id}/toggle-ban`,
      { method: "POST", token, body: "{}" },
    ),
  adminAuditLog: (token: string, action?: string) =>
    req<{ entries: AuditEntry[] }>(
      `/api/admin/audit${action ? `?action=${encodeURIComponent(action)}` : ""}`,
      { token },
    ),
};

export type AuditEntry = {
  id: number;
  actor: string | null;
  action: string;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AdminUser = {
  id: number;
  handle: string;
  trust_score: number;
  is_shadow_banned: boolean;
  is_verified: boolean;
  age_confirmed: boolean;
  created_at: string | null;
  last_seen: string | null;
};

export type VaultItem = {
  id: number;
  kind: "human" | "bot";
  other_handle: string;
  summary_text: string;
  started_at: string;
  ended_at: string | null;
};

export type AdminReport = {
  id: number;
  reporter: string | null;
  target: string | null;
  target_id: number | null;
  conversation_id: number | null;
  reason: string;
  note: string;
  status: "open" | "dismissed" | "actioned";
  created_at: string;
};

export type PersonaCard = {
  slug: string;
  name: string;
  avatar_url: string;
  persona_card: {
    age_vibe?: string;
    interests?: string[];
    tics?: string[];
  };
  spice_level: "sfw" | "flirty" | "spicy";
  allowed_tags: string[];
};

export type ChatMessage = {
  id: number;
  body: string;
  sent_at: string;
  is_me: boolean;
  is_persona: boolean;
  soft_flag: boolean;
};

export type ConversationPayload = {
  id: number;
  kind: "human" | "bot";
  other_handle: string;
  other_verified: boolean;
  started_at: string;
  ended_at: string | null;
  is_vaulted: boolean;
  messages: ChatMessage[];
};
