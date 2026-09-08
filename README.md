# Interview Prep Simulator

Multi-agent interview simulator: paste a job description + resume, get asked role-specific
questions, get scored internally (no live grading), and see the full breakdown at the end.
Full design in [interview-prep-simulator-plan.md](interview-prep-simulator-plan.md).

**Status: Phase 1 — core pipeline (no LangGraph yet).** Single question in, single answer out,
scored and stored but not returned. See the plan's Build Roadmap for what's next.

## Setup

### 1. Supabase project
1. Create a project at https://supabase.com/dashboard.
2. In the SQL Editor, run [backend/db/schema.sql](backend/db/schema.sql).
3. Under Project Settings → API, copy the **Project URL** and the **service_role** key
   (not `anon` — the backend needs write access).
4. Under Authentication → Users → Add user, create one test user and copy its UUID.
   Phase 1 has no login flow yet (that's Phase 2), so the demo script takes this UUID directly.

### 2. Gemini API key
Get one free at https://aistudio.google.com/apikey.

### 3. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # then fill in GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY
uvicorn app.main:app --reload
```

### 4. Run the Phase 1 proof
In another terminal, with the server running:
```bash
pip install requests   # if not already installed
python scripts/demo.py <the test user's UUID>
```
This creates a session (JD + resume → `analyze_profile` → one question), submits a
deliberately weak answer, and asserts the `/answer` response never contains a score or
feedback — even though both were computed and written to the `answers` table. Check the
Supabase table editor afterward to see the stored score/feedback.

## API (Phase 1 subset)

| Endpoint | Method | Returns score/feedback? |
|---|---|---|
| `/sessions` | POST | No — just the first question |
| `/sessions/{id}/answer` | POST | **No** — only `{recorded, has_next}` |

Full endpoint set (history, summary, trends) lands in later phases per the roadmap.
