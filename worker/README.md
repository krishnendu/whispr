# Whispr bot reply worker

Runs `apps.bots.runner.drain_orphans` in a loop, processing any `BotJob`
rows the Django process didn't finish.

Use this when you want guaranteed bot reply delivery. Without it, replies
fall back to:
1. The in-process thread inside the Django request handler (best effort).
2. The Vercel cron at `/api/cron/process-bot-jobs` (runs every minute, so
   replies stalled by step 1 land within ~60s).

## Run locally

```bash
cd <repo>
DATABASE_URL=postgres://... GROQ_API_KEY=... \
    backend/.venv/bin/python worker/run.py
```

## Deploy to Fly.io

```bash
cd worker
fly launch --copy-config --no-deploy   # accept defaults; declines DB attach
fly secrets set \
  DATABASE_URL='<neon url>' \
  GROQ_API_KEY='<groq key>' \
  GROQ_DEFAULT_MODEL='llama-3.3-70b-versatile' \
  DJANGO_SECRET_KEY='<random 50+ chars>' \
  REDIS_URL='<upstash url>'
fly deploy
```

The worker reads from the same Postgres the web tier writes to, so they
don't need to share infra — they share the BotJob queue.
