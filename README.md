# Interview Prep Simulator

Multi-agent interview simulator: paste a job description + resume, get asked role-specific
questions, get scored internally (no live grading), and see the full breakdown at the end.
Full design in [interview-prep-simulator-plan.md](interview-prep-simulator-plan.md).

**Status: Phase 4 — summarizer + results + trends.** When `route_after_eval` ends a session,
the graph now runs a `summarize_session` node — the first point anywhere in the app that a
score or pattern is ever revealed. The results screen shows the overall score, recurring
weaknesses across answers, and a full per-question breakdown; a history screen lists past
sessions with a score-over-time chart. LangGraph pipeline (Phase 3), frontend + auth (Phase 2)
landed earlier. See the plan's Build Roadmap for what's next (Phase 5: eval set + polish).

## Setup

### 1. Supabase project

1. Create a project at https://supabase.com/dashboard (free tier caps active projects per
   *owner*, not per org — if you hit that limit, pause/delete an old project or use a
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

## API

| Endpoint                       | Method | Returns score/feedback?              |
| ------------------------------- | ------ | ------------------------------------ |
| `/sessions`                     | POST   | No — just the first question         |
| `/sessions/{id}/answer`         | POST   | **No** — only `{recorded, has_next}` |
| `/sessions/{id}/next-question`  | GET    | No — just the next question, if any  |
| `/sessions/{id}/summary`        | GET    | **Yes** — overall score, patterns, full per-question breakdown |
| `/sessions`                     | GET    | No — session list for history        |
| `/stats/trends`                 | GET    | Yes (aggregate) — score trend across completed sessions |

`/sessions/{id}/summary` only returns data once the interview has actually ended — there's no
way to peek at scores mid-interview even by hitting the endpoint directly.
