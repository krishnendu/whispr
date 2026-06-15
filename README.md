# Whispr

> Talk to anyone. About anything. Without leaving a trace.

A web-first anonymous chat platform with tag-based matching, ephemeral messages, and a roster of conversational AI personas that step in when the human pool is dry.

See [`PLAN.md`](./PLAN.md) for the full product + architecture plan, and [`designs/`](./designs) for mockups.

## Stack
- Backend: Django 5 + DRF (deployed as Vercel serverless via `@vercel/python`)
- Frontend: Next.js 16 + Tailwind + App Router
- DB: Neon Postgres · Cache: Upstash Redis · Realtime: Ably
- AI: Groq (OpenAI-compatible) — Llama 3.3 default
- Auth: Google OAuth + magic links via Gmail SMTP
- Host: Vercel

## Layout
```
backend/   Django project (apps: accounts, chat, matching, bots, moderation, tags)
api/       Vercel serverless entrypoint → Django WSGI
frontend/  Next.js app
designs/   Mockups & brand
PLAN.md    Full plan
```

## Local dev

Copy env template, fill in services:

```bash
cp .env.example .env.local
# fill DATABASE_URL (Neon), REDIS_URL (Upstash), ABLY_API_KEY, GROQ_API_KEY,
# GOOGLE_OAUTH_*, EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
```

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver  # http://localhost:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

Smoke check: visit `http://localhost:8000/api/health` → `{"ok": true, "service": "whispr-api"}`.

## Status
Phase 0 — scaffolding & plan. Next up: auth, profiles, tags (Phase 1 in `PLAN.md`).
