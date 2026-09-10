# Merch Ops — Order Status & TNA Deadline SaaS

Multi-tenant app wrapping two LangGraph agents:

1. **Order Status Agent** — on-demand, multi-step: fetch order → fetch TNA → assess risk → compose answer.
2. **TNA Deadline Watcher** — scheduled, human-in-the-loop: scan calendar → draft reminder → **pause for human approval** → send or discard.

Stack: **Next.js** (frontend) · **FastAPI** (backend) · **Supabase** (Postgres + Auth) · **LangGraph + Groq** (agents).

---

## 1. Set up Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. In the SQL editor, run `backend/supabase/schema.sql`. This creates `tenants`, `profiles`, `orders`, `tna_calendar`, `assessments`, `tna_threads`, `notifications`, and Row Level Security policies.
3. Create at least one tenant and one user manually to start:
   ```sql
   insert into tenants (name) values ('Acme Apparel') returning id;
   -- sign up a user via Supabase Auth UI or supabase.auth.signUp(), then:
   insert into profiles (user_id, tenant_id, email)
   values ('<auth-user-uuid>', '<tenant-id-from-above>', 'you@acme.com');
   ```
4. Grab these values from **Project Settings → API**:
   - `SUPABASE_URL`
   - `SUPABASE_JWKS_URL` (`<project-url>/auth/v1/.well-known/jwks.json`)
5. Grab the Postgres connection string from **Project Settings → Database** (use the "Session pooler" URI for `DATABASE_URL`).

## 2. Backend — run locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Supabase, Groq, and CRON_SECRET values
uvicorn app.main:app --reload
```

API runs at `http://localhost:8000`. Check `http://localhost:8000/health`.

Key endpoints:
- `GET /orders` — list this tenant's orders with their latest assessment
- `POST /orders/{order_ref}/assess` — kicks off the Order Status Agent in the background, returns a `job_id`
- `GET /orders/assess/{job_id}` — poll for the result
- `POST /tna/scan` — runs the TNA Watcher once; pauses and returns `pending_approval` if risk is found
- `GET /approvals` — list drafts awaiting human approval
- `POST /approvals/{thread_id}/decide` — approve (sends) or reject (discards)

## 3. Frontend — run locally

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in Supabase + API URL
npm run dev
```

Runs at `http://localhost:3000`. Log in with the user you created in step 1.

## 4. Deploying for free

This stack can run entirely on free tiers while you build and test. Real limits and honest caveats on each:

| Piece | Free tier | The catch |
|---|---|---|
| Database + Auth | **Supabase Free** | Project auto-pauses after 7 days with zero traffic (data is kept, needs a manual resume) — solved by the cron ping below |
| LLM | **Groq Free** | 30 requests/min, ~100K tokens/day for Llama 3.3 70B — fine for building/demoing, not for real concurrent traffic |
| Backend | **Render Free Web Service** | Spins down after 15 min idle; ~30-60s cold start on the next request |
| Frontend | **Vercel Free (Hobby)** | Vercel's terms restrict Hobby to personal/non-commercial use — fine while building, but move to Pro ($20/mo) once this has paying customers |
| Scheduling | **GitHub Actions** (free) | Runs the daily scan and keeps Supabase awake in one workflow |

**Backend → Render:**
1. Push this repo to GitHub.
2. New Web Service on [render.com](https://render.com) → connect the repo → root directory `backend`.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add every value from `.env.example` as an environment variable in Render's dashboard (real values, not the placeholders). Set `ALLOWED_ORIGINS` to your Vercel URL once you have it.

**Frontend → Vercel:**
1. Import the repo at [vercel.com](https://vercel.com) → root directory `frontend`.
2. Add the three `NEXT_PUBLIC_*` vars from `.env.local.example`, pointing `NEXT_PUBLIC_API_BASE_URL` at your Render URL.
3. Deploy. Then go back to Render and update `ALLOWED_ORIGINS` to include the Vercel URL it gives you.

**Scheduling → GitHub Actions:**
The workflow at `.github/workflows/daily-tna-scan.yml` calls `POST /tna/scan-all` (loops every tenant, no user login needed — protected by `CRON_SECRET` instead) and pings Supabase so it doesn't pause. Add these as repo secrets under **Settings → Secrets and variables → Actions**:
- `BACKEND_URL` — your Render URL
- `CRON_SECRET` — must match the value in Render's env vars
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`

## 5. What's deliberately left as a v1 shortcut

- **Background jobs use FastAPI `BackgroundTasks`**, not Celery+Redis. Fine for launch; migrate to Celery when a single assessment run needs to survive an API server restart or you need to scale workers independently.
- **No billing yet.** The `tenants` table is intentionally plain right now — when you're ready to add Stripe, add `plan` and `stripe_customer_id` columns back and gate `/orders/{ref}/assess` and `/tna/scan` on plan/usage limits.
- **No LangSmith tracing wired up yet.** Add `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` env vars to get full visibility into every LLM call for free.
- **`send_reminder` writes to a `notifications` table only.** Wire it to Slack/email (e.g. Resend, Slack webhook) when you're ready to actually notify people outside the app.

## 6. File map

```
backend/
  app/
    main.py              FastAPI app + CORS
    config.py             env-driven settings
    db.py                  Postgres connection helpers
    auth.py               Supabase JWT verification + tenant resolution
    schemas.py           Pydantic request/response models
    graphs/
      order_status_graph.py   Agent 1
      tna_watcher_graph.py    Agent 2 (human-in-the-loop, Postgres checkpointer)
    routers/
      orders.py, tna.py, approvals.py
  supabase/schema.sql    tables + RLS policies

frontend/
  app/
    login/page.tsx
    dashboard/page.tsx    orders + on-demand assessment
    approvals/page.tsx    human-in-the-loop inbox
    components/Nav.tsx
  lib/
    supabaseClient.ts
    api.ts                 attaches Supabase JWT to backend calls
```
