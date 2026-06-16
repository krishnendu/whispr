# Whispr

> Talk to anyone. About anything. Without leaving a trace.

A web-first anonymous chat platform with tag-based matching, ephemeral messages, and a roster of conversational AI personas that step in when the human pool is dry.

See [`PLAN.md`](./PLAN.md) for the full product + architecture plan, and [`designs/`](./designs) for mockups.

## Stack
- **Backend:** Django 5 + DRF, deployed as Vercel serverless via `@vercel/python` (Fluid Compute).
- **Frontend:** Next.js 16 + Tailwind 4 + App Router.
- **DB:** Neon Postgres (SQLite fallback for first-run local dev).
- **Realtime:** Server-Sent Events (no Ably/WebSocket service required).
- **AI:** Groq (OpenAI-compatible) — Llama 3.3 by default, MockEngine fallback if no key.
- **Moderation:** Groq-as-judge on outbound persona text.
- **Auth:** Google OAuth + magic links via Gmail SMTP.
- **Host:** Vercel (web + Django serverless + cron).

## Layout
```
backend/   Django project (apps: accounts, chat, matching, bots, moderation, tags)
api/       Vercel serverless entrypoint → Django WSGI
frontend/  Next.js app
designs/   Mockups & brand
vercel.json  Routes /api/* → Django, else → Next.js. Includes daily cron.
```

## Local dev

```bash
cp .env.example .env.local
# At minimum fill DJANGO_SECRET_KEY. Everything else has sane fallbacks:
#   - DATABASE_URL not set → SQLite at backend/db.sqlite3
#   - GROQ_API_KEY not set → MockEngine (replies are echoed templates)
#   - EMAIL_HOST_USER not set → magic-link emails return the link inline
#     in the API response, so onboarding works without SMTP

# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_tags
.venv/bin/python manage.py seed_personas
.venv/bin/python manage.py runserver   # http://localhost:8000

# Frontend (new shell)
cd frontend
npm install
npm run dev                            # http://localhost:3000
```

Smoke: `curl http://localhost:8000/api/health` → `{"ok": true}`.

### Making yourself an operator (to see `/admin/reports`)
```bash
cd backend
.venv/bin/python manage.py shell -c "from django.contrib.auth import get_user_model as U; u=U().objects.get(handle='your-handle'); u.is_operator=True; u.save()"
```

## Deploying to Vercel

1. **Provision a Neon Postgres database.** Vercel Marketplace → Neon → create. Copy the pooled connection string (looks like `postgres://…@…neon.tech/…?sslmode=require`).
2. **Get the API keys you'll need:**
   - `GROQ_API_KEY` from console.groq.com (free tier covers v0).
   - Google OAuth client at console.cloud.google.com — set redirect URI to `https://<your-vercel-domain>/auth/callback/google`.
   - Gmail App Password at myaccount.google.com → Security → 2FA → App passwords (requires 2FA on the account).
3. **Generate a `CRON_SECRET`:** `openssl rand -hex 32`. Vercel Cron will send it as `Authorization: Bearer <secret>`.
4. **Push to GitHub, then `vercel link` this directory.**
5. **Set env vars** in Vercel project settings (or `vercel env add`):
   - `DJANGO_SECRET_KEY` (50+ random chars)
   - `DJANGO_DEBUG=false`
   - `ALLOWED_HOSTS=<your-domain>,.vercel.app`
   - `CORS_ALLOWED_ORIGINS=https://<your-domain>`
   - `DATABASE_URL`
   - `GROQ_API_KEY`
   - `CRON_SECRET`
   - `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`
   - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
   - `NEXT_PUBLIC_API_BASE=https://<your-domain>`
6. **First deploy.** `vercel --prod`. Then run migrations + seeds:
   ```bash
   # Pull prod envs to a local file
   vercel env pull .env.production
   # Run migrations against prod Neon DB from your machine
   cd backend && env $(cat ../.env.production | xargs) .venv/bin/python manage.py migrate
   env $(cat ../.env.production | xargs) .venv/bin/python manage.py seed_tags
   env $(cat ../.env.production | xargs) .venv/bin/python manage.py seed_personas
   ```

### Known caveats for production

- **Bot reply runner uses a Python thread.** It works fine on a single long-lived process (local dev, Fly/Railway). On Vercel serverless, threads may not survive the function instance — Fluid Compute reuses instances but doesn't guarantee thread lifetime. If persona replies feel flaky in prod, the plan's next step is a real worker (Fly/Railway box, or migrate to Vercel Queues). The thread approach is intentional for v0 simplicity.
- **SSE function lifetime.** The stream exits at 270s and the browser reconnects via `Last-Event-ID`. Vercel's 300s default function timeout fits, but this means each open chat is one active function invocation — keep an eye on usage if traffic grows.
- **Daily cron.** `vercel.json` registers `/api/cron/cleanup` to run at 04:00 UTC. It closes idle conversations, drops raw text from ended ones (keeps the `summary_text` column), and clears stale magic-link tokens + abandoned match queue entries.
- **No Redis yet.** Rate limits, presence, and the hot-message buffer in the plan all need Upstash. For v0 the polling/PG path is sufficient. Wire `REDIS_URL` later and the relevant call sites will switch over.

## Status

- Phase 0 — scaffold ✓
- Phase 1 — auth + profiles + tags ✓
- Phase 2 — human↔human matching + chat (SSE realtime, ~250ms latency) ✓
- Phase 3 — persona surface (Groq + humanizer) ✓
- Phase 4 — bot fallback when human pool is dry ✓
- Phase 5 — moderation + reporting + block list + admin queue ✓
- Phase 6 — anti-bot signals & rate limits (next, needs Upstash)
- Phase 7 — polish & PWA & deploy (mostly here: manifest, error boundaries, cron, deploy docs ✓)
