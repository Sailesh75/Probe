# Interview Prep Simulator

Multi-agent interview simulator: paste a job description + resume, get asked role-specific
questions, get scored internally (no live grading), and see the full breakdown at the end.
Full design in [interview-prep-simulator-plan.md](interview-prep-simulator-plan.md).

**Status: Phase 5 — polish + eval.** All four core phases are built: LangGraph pipeline with
real follow-up branching (Phase 3), auth + React frontend (Phase 2), and a summarizer +
results/history/trends screens (Phase 4). Phase 5 adds an eval set proving the evaluator's
scoring tracks human judgment — see [eval/README.md](eval/README.md) for methodology and
results (80% exact agreement, 100% within one point, across 10 deliberately varied answers).

## Architecture

```
paste JD + resume
       │
       ▼
┌─────────────────────┐
│ analyze_profile      │  node 0 — runs once; the JD/resume pairing is a real input to
└──────────┬───────────┘  question selection, not two textareas concatenated into a prompt
           ▼
┌─────────────────────┐
│ generate_question    │◄─┐  prefers gap_areas; follow-up mode probes deeper on the same
└──────────┬───────────┘  │  target_area instead of asking a fresh question
           ▼               │
    [user answers]         │
           ▼               │
┌─────────────────────┐    │
│ evaluate_answer       │   │  INTERNAL ONLY — appends to the transcript, never
└──────────┬───────────┘    │  reaches the client until summarize_session runs
           ▼               │
┌─────────────────────┐    │
│ route_after_eval      │───┘  the real branch: follow up (capped) / next question
└──────────┬───────────┘       (capped) / end — decided by the evaluator's actual output
           ▼ (end)
┌─────────────────────┐
│ summarize_session     │  first point anywhere scores/patterns are revealed
└──────────────────────┘
```

Backend: FastAPI + LangGraph (`backend/app/graph/`) + Gemini (`gemini-3.6-flash`) + Supabase
(Postgres + auth). Frontend: React + Vite, no state library — Supabase's session and a bit of
router state cover it. Full endpoint list in [API](#api) below.

### Decisions worth knowing about

- **The graph runs per-request, not as one long-lived process.** Each HTTP call re-hydrates
  just enough `InterviewState` from Supabase (transcript, follow-up count, etc.) and runs one
  of two compiled graphs to completion synchronously. No LangGraph checkpointer — Supabase's
  tables are the actual durable state, which is simpler and avoids a second source of truth.
- **The no-live-grading rule is enforced at the API boundary, not the UI.** `/answer` and
  `/next-question` are structurally incapable of returning a score — the response models don't
  have the field. Hiding it only in the frontend would leave it visible to anyone hitting the
  API directly.
- **`user_id` always comes from a verified Supabase JWT, never a request body field.** An
  earlier version trusted a client-supplied `user_id`; that's spoofable, so `get_current_user_id`
  verifies the token server-side before anything else runs.
- **Gemini model pinned to `gemini-3.6-flash`, not the plan's original `gemini-2.0-flash`** —
  that model (and its stable successor `2.5-flash`) were both retired for new users during
  development. Structured output calls also retry transient 429/5xx errors with backoff and
  carry an explicit 30s timeout — the client library has no default timeout, which caused a
  real 5+ minute hang during testing before this was added.
- **`session_summaries.patterns` is a jsonb blob holding `{overall_feedback, issues}`**, not a
  bare pattern list — reusing the schema's loose jsonb column instead of an `ALTER TABLE` for
  one extra string.
- **Score trends group by role, not the plan's sketched behavioral/technical/system-design
  category** — that split needs a question-classification step nothing upstream produces yet;
  role is what the data already has without inventing new machinery for it.

## Setup

### 1. Supabase project

1. Create a project at https://supabase.com/dashboard (free tier caps active projects per
   _owner_, not per org — if you hit that limit, pause/delete an old project or use a
   different account).
2. In the SQL Editor, run [backend/db/schema.sql](backend/db/schema.sql).
3. Under Project Settings → API, copy the **Project URL** and both keys:
   - **service_role** → goes in `backend/.env` (full write access, server-only, never expose it)
   - **anon public** → goes in `frontend/.env` (safe to expose client-side; Row Level Security
     in `schema.sql` scopes what it can actually do)

### 2. Gemini API key

Get one free at https://aistudio.google.com/apikey. **Free tier is capped at 20
requests/day per model** — each session start costs 2 calls (`analyze_profile` +
`generate_question`) and each answer costs 1-2 more, so a handful of test interviews will
burn through it fast. If you hit `429 RESOURCE_EXHAUSTED`, that's this daily cap, not a bug —
wait for it to reset or use a different key.

### 3. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # then fill in GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY
uvicorn app.main:app --reload
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env          # fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL
npm run dev
```

Open the printed localhost URL, sign up (Supabase sends a confirmation email), sign in, paste
a JD + resume, and go through the interview. Score/feedback are computed per answer but never
shown — that's enforced at the API layer, not just hidden in the UI.

### 5. Run the end-to-end proof

With the backend running:

```bash
pip install requests supabase   # if not already installed
python scripts/demo.py <email> <password>   # a confirmed Supabase user (e.g. one you signed up via the frontend)
```

This runs a full interview via the real HTTP API — session creation, then answer/next-question
turns in a loop until `route_after_eval` ends the session — asserting at every step that the
`/answer` response never contains a score, feedback, or the next question's text.

### 6. Run the eval set

No running server needed — these import the backend code directly:

```bash
python eval/run_evaluator_eval.py   # scores 10 pre-judged sample answers, reports agreement
python eval/run_profile_eval.py     # spot-checks analyze_profile on 3 JD/resume pairs
```

See [eval/README.md](eval/README.md) for methodology and results.

## API

| Endpoint                       | Method | Returns score/feedback?                                        |
| ------------------------------ | ------ | -------------------------------------------------------------- |
| `/sessions`                    | POST   | No — just the first question                                   |
| `/sessions/{id}/answer`        | POST   | **No** — only `{recorded, has_next}`                           |
| `/sessions/{id}/next-question` | GET    | No — just the next question, if any                            |
| `/sessions/{id}/summary`       | GET    | **Yes** — overall score, patterns, full per-question breakdown |
| `/sessions`                    | GET    | No — session list for history                                  |
| `/stats/trends`                | GET    | Yes (aggregate) — score trend across completed sessions        |

`/sessions/{id}/summary` only returns data once the interview has actually ended — there's no
way to peek at scores mid-interview even by hitting the endpoint directly.
