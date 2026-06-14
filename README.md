# Whispr

> Talk to anyone. About anything. Without leaving a trace.

A web-first anonymous chat platform with tag-based matching, ephemeral messages, and a roster of conversational AI personas that step in when the human pool is dry.

See [`PLAN.md`](./PLAN.md) for the full product + architecture plan, and [`designs/`](./designs) for mockups.

## Stack
- Backend: Django 5 + DRF (deployed as Vercel serverless via `@vercel/python`)
- Frontend: Next.js 15 + Tailwind + shadcn/ui
- DB: Neon Postgres · Cache: Upstash Redis · Realtime: Ably
- AI: Anthropic Claude (Sonnet 4.6 / Haiku 4.5) with prompt caching
- Host: Vercel

## Layout
```
backend/   Django project (apps: accounts, chat, matching, bots, moderation, tags)
api/       Vercel serverless entrypoint → Django WSGI
frontend/  Next.js app
designs/   Mockups & brand
PLAN.md    Full plan
```

## Status
Phase 0 — scaffolding & plan. See the roadmap in `PLAN.md`.
