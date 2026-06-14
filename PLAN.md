# Whispr — Anonymous Chat Webapp

> "Whisper into the void. Someone always whispers back."

A web-first anonymous chat platform inspired by Antiland, where users can drop in, pick a vibe (tags), and talk — sometimes with other humans, sometimes with carefully-crafted AI personas that feel indistinguishable from real people. Conversations are ephemeral by design; old messages rotate out so the platform stays light and the user feels safe.

---

## 1. Product Vision

**Tagline:** *Talk to anyone. About anything. Without leaving a trace.*

**Core promises to the user:**
- Zero-friction onboarding (no real name, no phone, just a handle + vibe).
- Always-on conversation — even at 3am, someone is there.
- Pick your mood via **tags** (chill, flirty, philosophical, gaming, late-night, vent, etc.) and get matched.
- Messages auto-evaporate; nothing follows you around.
- Tools to keep real bots/spammers out of the human pool.

**Core promises to the operator (us):**
- Bots are first-class citizens of the platform, not a fallback. They're warm bodies during cold-start, off-hours, or when no one matching a niche tag is online.
- Tight DB footprint via aggressive message rotation.
- Clean separation of "human↔human" vs "human↔AI" matching pools so bot quality can be tuned without polluting real conversations.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend framework | **Django 5 + Django REST Framework** | Mature, batteries-included auth, ORM, admin for ops. |
| Realtime | **Django Channels (ASGI)** or **Pusher/Ably** SaaS | Vercel's serverless model makes long-lived WS painful; either run ASGI worker on a small VM (Railway/Fly) OR use a managed WS service called from Vercel functions. **Decision: start with Ably (managed) for v1 to keep Vercel-only deploy.** |
| DB | **Postgres (Neon or Supabase via Vercel Marketplace)** | Serverless-friendly, branching for previews. |
| Cache / ephemeral | **Upstash Redis** | Active message buffer, rate-limit counters, presence. |
| Frontend | **Next.js 15 (App Router) + React + Tailwind + shadcn/ui** | Vercel-native, fast iteration. |
| AI bots | **Anthropic Claude (Sonnet 4.6 default, Haiku 4.5 for cheap/throughput)** with per-persona system prompts + prompt caching | Quality + tone control + caching keeps cost down. |
| Moderation | OpenAI Moderation API OR Claude as judge OR Perspective API | Layered. |
| Auth | Django allauth + magic-link / OAuth (Google, Apple) | Anonymous handle, but a real underlying account for ban tracking. |
| Hosting | **Vercel** (frontend + Django via @vercel/python serverless) | Per the brief. |
| Realtime worker (if self-hosted Channels) | Railway / Fly.io | Vercel can't run ASGI workers indefinitely. |

### Why this Vercel shape works for Django

Vercel runs Django as serverless functions via `vercel.json` rewrites pointing to `api/index.py` which exposes the WSGI app. This is fine for REST endpoints. Realtime chat is the hard part — handled by **Ably channels** (managed pub/sub), authorized via a short-lived JWT minted by a Django endpoint. Result: zero realtime infrastructure to babysit.

---

## 3. Feature Set

### 3.1 Onboarding (no friction)
- Pick a handle (with profanity filter), age confirmation (18+ for spicy mode), choose 3–5 starting tags, optional gender/pronouns.
- Optional: link Google for "real account" badge — small trust boost in matching.

### 3.2 Tags & Matching
- Curated tag list + free-tag (rate-limited new-tag creation).
- Tag categories: *Mood, Topic, Spice Level, Language, Region, Time-of-day*.
- Matching engine:
  1. Look up online humans with ≥1 tag overlap, sort by overlap count + recency + reputation.
  2. If pool is empty / user has waited > T seconds / user opted-in to "always answered", route to a bot whose persona matches the tag set.
  3. The user never sees this branch — both routes drop them into the same chat UI.

### 3.3 Chat
- 1-on-1 ephemeral chat rooms.
- "Tap to reveal" for borderline messages (consent-gated content).
- Stickers / GIFs (Giphy passthrough) — bots use them too, naturally.
- Typing indicators (with humanized cadence for bots).
- End conversation / reroll partner.

### 3.4 Bot Personas (the secret sauce)
- Curated persona library (10–50 at launch): each has a name, age, location-vibe, interests, speech tics, an LLM system prompt, allowed spice level, and example dialogues for few-shot.
- Per-persona memory: 20–50 messages of rolling window per user-persona pair, stored in Redis with TTL. Long-term "facts I learned about this user" stored as a tiny key-value blob.
- Cadence humanizer: pacing layer that delays sends 1–6s per message based on length, inserts typos at <1%, sometimes "..." pauses, sometimes splits a long reply into 2–3 bubbles. **This is what makes the AI feel real.**
- Spice gating: per-persona policy + user's confirmed 18+ flag + region check. Below threshold, persona stays SFW; above, persona escalates within policy. Hard rules (no minors, no real violence, etc.) are baked into the system prompt and double-checked by a moderation pass before send.
- Provider abstraction: `BotEngine` interface so we can swap Claude / OpenAI / local model.

### 3.5 Anti-spam / Anti-bot (against *unwanted* bots — protecting the human pool)
- Behavioral signals: typing speed, paste vs type ratio, time-on-screen jitter, message entropy, URL/repetition rate.
- Phone-number / OAuth-required to enter the "verified human" pool (matching boost).
- Trust score per account (0–100); decays on reports, climbs on positive interactions.
- Rate limits at every layer (Redis sliding window): messages/min, new-chat/min, new-account/IP/day.
- CAPTCHA on suspicious patterns.
- Report button → moderation queue → shadow-ban then full ban.
- Honeypot tags / bait messages to detect crawler bots.
- Device fingerprint (FingerprintJS open-source) to catch ban-evasion.

### 3.6 Message Storage & Rotation (limited DB by design)
- **Hot store (Redis):** last N=50 messages per active conversation, TTL 24h after last activity.
- **Warm store (Postgres):** only the last N=20 messages per conversation are persisted, oldest pruned on every insert (trigger or app-level). Conversations idle > 7 days are fully purged.
- Daily cron prunes orphaned data.
- Aggregates (counts, durations) kept long-term for analytics; raw text isn't.
- User can "save" up to 10 conversations to a personal vault (still capped, still rotates oldest-out).

### 3.7 Safety / Reporting
- One-tap report with reason.
- Auto-moderate every outgoing AND incoming message through a moderation layer (Claude-as-judge or OpenAI moderation).
- Block list per user.
- "Panic" button hides chat and ends session.

---

## 4. Data Model (high level)

```
User
  id, handle, email_hash, oauth_provider, age_confirmed, trust_score,
  is_shadow_banned, created_at, last_seen, locale

Tag
  id, slug, category, is_user_created, created_by, usage_count

UserTag
  user_id, tag_id, weight, added_at

Persona  (bots)
  id, name, system_prompt_ref, persona_card_json, model_id,
  spice_level, allowed_tags[], avatar_url, is_active

Conversation
  id, kind (human|bot), participant_a, participant_b_or_persona,
  started_at, last_activity_at, ended_at, is_vaulted_by_a, is_vaulted_by_b

Message    (rotating; capped per conversation)
  id, conversation_id, sender_id, body, sent_at, mod_flags, is_redacted

PersonaMemory  (Redis primary; small KV blob in PG as fallback)
  user_id + persona_id -> last_facts, last_window_summary

MatchQueue (Redis sorted set, ephemeral)

Report, Ban, AuditLog (standard moderation tables)
```

---

## 5. API Surface (Django REST + WS via Ably)

REST (Vercel-friendly):
- `POST /api/auth/oauth/start|callback`
- `POST /api/me`  (profile, tags)
- `GET  /api/tags?query=` / `POST /api/tags` (rate-limited)
- `POST /api/match/start { tags, mode }` → returns conversation_id (human or bot, opaque to client)
- `POST /api/match/cancel`
- `GET  /api/conversations/:id`  (recent messages from Postgres+Redis merge)
- `POST /api/conversations/:id/messages { body }`  (server dispatches: human→Ably, bot→queue→BotEngine→Ably)
- `POST /api/conversations/:id/end`
- `POST /api/conversations/:id/save` (vault)
- `POST /api/report`
- `GET  /api/ably-token` (signs a short-lived token for that user+conversation)

Background jobs (Vercel Cron or external worker):
- bot reply worker (consumes a Redis queue, calls Claude, humanizes, posts via Ably + DB)
- message-rotation cron (every minute: trim per-conversation tail past N=20)
- conversation-purge cron (daily: drop idle > 7d)
- moderation-sweep cron (re-scores flagged accounts)

---

## 6. Bot Reply Pipeline (detailed)

```
[user msg POSTed]
   ↓ Django saves to Postgres (rotates tail)
   ↓ Publishes to Ably channel (other side sees it instantly)
   ↓ If conversation.kind == bot:
        enqueue {conversation_id, persona_id, user_msg} on Redis stream
   ↓
[bot worker]  (Vercel cron tick OR small Fly.io worker for tighter latency)
   ↓ Loads persona card + last 20 msgs + persona_memory facts
   ↓ Builds prompt (cached system block + dynamic block)
   ↓ Calls Claude (Sonnet for premium personas, Haiku for cheap pool)
   ↓ Moderation pass on output
   ↓ Humanizer: split into 1–3 bubbles, schedule delays (Redis ZADD with future ts)
   ↓ Sender loop: at each scheduled ts, post bubble via Ably + save to PG (rotating)
```

Cost control:
- Prompt caching on persona system prompt (5min TTL, huge savings).
- Haiku 4.5 for tier-1 personas, Sonnet 4.6 for "premium" personas, Opus reserved for high-value moments only.
- Bot only replies when user has sent a message (no proactive spam unless we explicitly want "re-engagement DMs").
- Hard per-user daily token cap → fallback to "I gotta run, ttyl" graceful exit.

---

## 7. Frontend (Next.js on Vercel)

Routes (App Router):
- `/` — landing + sign-in
- `/onboarding` — handle, age, tags
- `/home` — current vibe + "find someone" CTA + recent vaulted chats
- `/chat/[id]` — chat UI (Ably subscription, optimistic send, typing indicators)
- `/discover` — tag browse
- `/settings` — profile, blocklist, danger zone (delete account)
- `/report/[id]` — modal

Design system:
- Tailwind + shadcn/ui base, custom theme (see `designs/07-color-palette.svg`)
- Glassy dark mode default, optional light
- Mobile-first; PWA-installable

---

## 8. Vercel Deployment Shape

```
whispr/
├── backend/                  # Django project
│   ├── whispr/               # settings, urls
│   ├── apps/
│   │   ├── accounts/
│   │   ├── chat/
│   │   ├── matching/
│   │   ├── bots/
│   │   ├── moderation/
│   │   └── tags/
│   ├── manage.py
│   └── requirements.txt
├── api/
│   └── index.py              # Vercel serverless entrypoint → Django WSGI
├── frontend/                 # Next.js app
│   ├── app/
│   ├── components/
│   └── package.json
├── vercel.json               # routes: /api/* → api/index.py, else → frontend
├── designs/                  # mockups (this folder)
└── PLAN.md                   # this file
```

`vercel.json` sketch:
```jsonc
{
  "builds": [
    { "src": "api/index.py", "use": "@vercel/python" },
    { "src": "frontend/package.json", "use": "@vercel/next" }
  ],
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/index.py" },
    { "source": "/(.*)",     "destination": "/frontend/$1" }
  ]
}
```

Env vars (Vercel project settings):
- `DATABASE_URL` (Neon)
- `REDIS_URL` (Upstash)
- `ABLY_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_MOD_API_KEY` (or skip)
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `ALLOWED_HOSTS`
- `GOOGLE_OAUTH_*`

---

## 9. Build Roadmap (phased)

**Phase 0 — Skeleton (this commit)**
- Repo scaffolding, plan, designs, Vercel config stub.

**Phase 1 — Auth + Profiles + Tags**
- Django models, OAuth, onboarding flow on Next.js.

**Phase 2 — Human↔Human matching + chat (Ably)**
- Match queue, chat UI, message persistence with rotation policy.

**Phase 3 — Bot engine v1**
- Persona model, Claude integration, humanizer, 5 launch personas.

**Phase 4 — Routing intelligence**
- Decide human-vs-bot per request based on pool, latency, opt-in.

**Phase 5 — Moderation + reporting**
- In/out moderation, report queue, trust score, shadow-ban.

**Phase 6 — Anti-bot signals & rate limits**
- Behavioral signals, fingerprinting, CAPTCHA flows.

**Phase 7 — Polish + PWA + launch**

---

## 10. Legal / Disclosure Considerations (read before launch)

Several jurisdictions now require disclosure that you're talking to AI:
- **California SB-1001 (Bolstering Online Transparency Act)** — bots used to incentivize a purchase or influence an election must disclose. A safe interpretation extends further.
- **EU AI Act, Article 50** — providers of AI systems that interact with people must inform the user.
- **FTC** guidance treats undisclosed AI as potentially deceptive.

Practical paths the operator can choose between:
1. **Full disclosure** ("You may be talking to AI") in TOS + a subtle in-chat indicator. Loses some magic but is safest.
2. **Region-gated disclosure** — show explicit notice in EU/CA, none elsewhere. Still legally fragile.
3. **Opt-in "AI companion" mode** — user explicitly chooses to talk to a persona; the platform is then a companion app like Replika, which is legally well-trodden. This is the recommended path: keep the "anonymous human chat" pool real, and offer a separate "Personas" surface for AI companions.

**Adult content:** if spice mode is enabled, mandatory age-gate, region block where required (many US states now require ID checks), and content boundaries hard-coded (absolute no minors, no non-consent, no real-person impersonation).

The code will be built so disclosure / persona-mode can be flipped on per region without rewrites.

---

## 11. What "done" looks like

- A user lands on Whispr, picks 3 tags, hits "find someone", and within 5 seconds is in a chat that feels human.
- They can't tell whether it's a bot or a person (in regions where that's permitted), and when it's a person, the experience is great because spammers were filtered out.
- Their conversation history naturally fades within a week, keeping the DB tiny and the user safe.
- The operator can ship new personas, tags, and policies without touching frontend code.
