# Interview Prep Simulator

Multi-agent interview simulator: paste a job description + resume, get asked role-specific
questions, get scored internally (no live grading), and see the full breakdown at the end.

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

Two optional inputs shape the interview without changing its core targeting: a resume can be
pasted or uploaded as PDF/DOCX (parsed server-side, dropped into the same editable field for
review), and pasting a company's real interview questions (e.g. from Glassdoor) shifts the
interviewer's tone/phrasing to match that company while still targeting the resume/JD gaps.
Answers can be typed or spoken (🎤 records, transcribes via Gemini's audio input, and drops the
text into the same editable field); questions can be read aloud via the browser's built-in
speech synthesis.

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
- **Gemini model pinned to `gemini-3.6-flash`, with same-provider fallback models behind it.**
  Earlier picks (`gemini-2.0-flash`, then its stable successor `2.5-flash`) were both retired
  for new users during development, and "high demand" 503s from Google's side are common
  enough to hit in normal use. Rather than just retrying the same overloaded model, a
  persistently unavailable model now falls through to `gemini-flash-lite-latest` then
  `gemini-3.1-flash-lite` — both verified live and structured-output-capable — before giving
  up. Considered a cross-provider fallback (e.g. DeepSeek) too, but that needs a separate
  account/key, isn't actually free long-term (a one-time trial credit, then paid), needs its
  own JSON-mode code path instead of Gemini's native schema enforcement, and wouldn't cover
  audio transcription — a same-provider fallback fixes the actual failure mode (one model
  overloaded) for free. Structured output calls also retry transient 429/5xx errors with
  backoff and carry an explicit 30s timeout — the client library has no default timeout, which
  caused a real 5+ minute hang during testing before this was added.
- **`session_summaries.patterns` is a jsonb blob holding `{overall_feedback, issues}`**, not a
  bare pattern list — reusing the schema's loose jsonb column instead of an `ALTER TABLE` for
  one extra string.
- **Score trends group by role**, not a finer behavioral/technical/system-design category —
  that split needs a question-classification step nothing upstream produces yet; role is what
  the data already has without inventing new machinery for it.
- **Voice transcription reuses Gemini instead of a separate Whisper API** — verified
  `gemini-3.6-flash` transcribes real speech correctly with the same key everything else uses,
  so voice input needed zero new setup (no OpenAI account/billing). Uploaded resumes and
  recorded answers both follow the same rule: the extracted/transcribed text lands in an
  editable field for review, never submitted automatically — both parsing and transcription
  can be wrong.
- **Company-style mode blends style with targeting, not one or the other.** The prompt is
  explicit that pasted questions set tone/phrasing/emphasis, not a literal question bank to
  reuse — verified against a real Gemini call: with a "design a system that handles 1M
  req/sec" style sample, the generated question kept probing the actual Kafka gap but shifted
  to matching system-design phrasing instead of the plain "have you used Kafka" default.

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
a JD + resume (or upload a PDF/DOCX), and go through the interview — typed or spoken (the 🎤
button needs mic permission, which browsers only grant on `localhost` or HTTPS, so this works
in local dev and will keep working once deployed, just not over plain HTTP). Score/feedback
are computed per answer but never shown — that's enforced at the API layer, not just hidden in
the UI.

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

See [Eval results](#eval-results) below for methodology and results.

## API

| Endpoint                       | Method | Returns score/feedback?                                          |
| ------------------------------ | ------ | ------------------------------------------------------------------ |
| `/sessions`                    | POST   | No — just the first question (`company_style_text` is optional) |
| `/sessions/{id}/answer`        | POST   | **No** — only `{recorded, has_next}`                             |
| `/sessions/{id}/next-question` | GET    | No — just the next question, if any                              |
| `/sessions/{id}/summary`       | GET    | **Yes** — overall score, patterns, full per-question breakdown   |
| `/sessions`                    | GET    | No — session list for history                                    |
| `/stats/trends`                | GET    | Yes (aggregate) — score trend across completed sessions          |
| `/resume/parse`                | POST   | No — extracted resume text (PDF/DOCX)                            |
| `/voice/transcribe`            | POST   | No — transcribed answer text                                     |

`/sessions/{id}/summary` only returns data once the interview has actually ended — there's no
way to peek at scores mid-interview even by hitting the endpoint directly.

## Eval results

Does the evaluator's scoring match human judgment, and does `analyze_profile` correctly flag
gaps (without inventing ones that aren't there)?

**Methodology.** [eval/sample_answers.jsonl](eval/sample_answers.jsonl) (10 items): each answer
was written with an `expected_score` and `rationale` decided _before_ running it through the
model — spanning correct-and-well-structured, correct-but-poorly-structured, confidently
wrong, buzzword-with-no-substance, missing the STAR "Result" step, and a resume claim that
doesn't hold up under a follow-up probe. That variety matters more than volume: 10 items
covering distinct failure modes says more than 30 near-duplicates.
[eval/sample_profiles.jsonl](eval/sample_profiles.jsonl) (3 items): a clean match, a near-total
mismatch, and a realistic mixed case, checking specifically that `analyze_profile` doesn't
fabricate gaps for a resume that genuinely covers the JD, or inflate weak evidence (one ML
course) into a real strength. Both eval scripts write results incrementally to
`eval/results/*.jsonl` — a Gemini free-tier quota failure partway through leaves completed
items on disk instead of losing the whole run, which is exactly what happened on the profile
eval below.

**Evaluator agreement:**

| Metric              | Result       |
| ------------------- | ------------ |
| Exact score match   | 8/10 (80%)   |
| Within 1 point      | 10/10 (100%) |
| Mean absolute error | 0.20         |

Both disagreements turned out to be defensible, not evaluator flaws:

- **`star_missing_result`** (expected 3, got 2) — the model's reasoning went further than mine:
  it penalized not just the missing Result step but the underlying behavior (escalating to a
  tech lead instead of resolving the disagreement directly). A stricter but fair read.
- **`short_but_complete`** (expected 4, got 5) — my own rationale for this item said brevity
  shouldn't be penalized when the question doesn't call for depth. The model applied that
  principle more consistently than I did and scored it a clean 5.

No disagreement involved the model being fooled by confident-but-wrong content or buzzword
fluency — `confident_but_wrong` and `buzzword_no_substance` both scored a correct 1, and
`claims_resume_skill_failed_probe` (a resume claim that doesn't hold up under a follow-up
probe) also scored 1 with feedback that named the gap explicitly rather than just calling it
"vague."

**Profile spot-check:**

- **`strong_match`** — `gap_areas: []`. Every JD requirement mapped directly to a resume
  strength; no fabricated gaps to manufacture something to say.
- **`weak_match`** — `strength_areas: []`. The one ML course wasn't inflated into a real
  strength, and all three JD requirements were correctly flagged as gaps.
- **`mixed_realistic`** — hit the daily quota after 2/3 items. This exact JD/resume pair was
  reused constantly through manual testing, though, and consistently identified Kafka as the
  gap area and Python/AWS ownership as the strengths every time it ran during development.
  Re-running it formally once quota resets would close this out, but the behavior is already
  well-evidenced.

**Caveat:** this ran against `gemini-3.6-flash` on one day, mid free-tier-quota constraints.
It's a directional signal ("the evaluator's judgment tracks a human's on a deliberately varied
set"), not a statistically rigorous benchmark — a real eval suite would need more items per
failure mode and multiple runs to check consistency.
