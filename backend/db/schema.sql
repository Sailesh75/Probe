-- Phase 1 schema for agentic-interview-prep
-- Run this in the Supabase SQL Editor (Project -> SQL Editor -> New query).
-- users are handled by Supabase Auth automatically (auth.users)

create table if not exists sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  role text not null,               -- e.g. "SWE", "Data Analyst"
  jd_text text,
  resume_text text,
  company_style_text text,          -- optional: pasted real questions (e.g. Glassdoor) to mimic
  jd_requirements jsonb,             -- extracted by analyze_profile
  resume_highlights jsonb,
  gap_areas jsonb,
  strength_areas jsonb,
  created_at timestamptz default now(),
  status text default 'in_progress'  -- in_progress | completed
);

create table if not exists questions (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references sessions not null,
  question_text text not null,
  target_area text,                 -- which gap/strength area this question probed, if any
  is_followup boolean default false,
  parent_question_id uuid references questions,  -- null if not a follow-up
  order_index int not null
);

create table if not exists answers (
  id uuid primary key default gen_random_uuid(),
  question_id uuid references questions not null,
  answer_text text not null,
  score numeric,             -- 1-5, written at answer time but not shown to the user until summary
  feedback text,
  needs_followup boolean,
  created_at timestamptz default now()
);

create table if not exists session_summaries (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references sessions not null,
  overall_score numeric,
  patterns jsonb,            -- e.g. [{issue: "skips STAR result step", count: 3}]
  created_at timestamptz default now()
);

-- Row Level Security: users should only see their own sessions.
-- Phase 1's backend uses the service_role key (bypasses RLS) so this isn't a blocker yet,
-- but enabling it now means it's already correct once the frontend talks to Supabase directly.
alter table sessions enable row level security;

create policy "Users can manage their own sessions"
  on sessions for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
