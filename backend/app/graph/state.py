"""State shape for the Phase 3 LangGraph pipeline, per the plan's section 4 design.

Each HTTP request re-hydrates just enough of this from Supabase to run one graph
invocation (see pipeline.py) — there's no long-lived graph process or checkpointer
spanning requests. Supabase's `sessions`/`questions`/`answers` tables are the durable
state; this TypedDict is the graph's working memory for a single turn.
"""

from typing import TypedDict

# How many fresh (non-followup) questions make up one interview, and how many
# consecutive follow-ups the evaluator can trigger before we move on regardless.
MAX_QUESTIONS_PER_SESSION = 5
MAX_FOLLOWUPS_PER_QUESTION = 2


class SessionProfile(TypedDict):
    jd_text: str
    resume_text: str
    jd_requirements: list[str]
    resume_highlights: list[str]
    gap_areas: list[str]
    strength_areas: list[str]


class InterviewState(TypedDict):
    role: str
    profile: SessionProfile
    asked_questions: list[str]  # question_text already asked, so generate_question avoids repeats
    current_question: str
    current_question_target: str
    is_followup: bool
    followup_count: int  # consecutive follow-ups already asked for the current fresh question
    questions_asked: int  # fresh (non-followup) questions asked so far, including the current one
    user_answer: str
    eval_result: dict | None  # {score, feedback, needs_followup} — set by evaluate_answer_node
    has_next: bool  # set by the answer-turn graph: did routing produce another question?
    transcript: list[dict]  # every prior {question, target_area, is_followup, answer, score,
    # feedback, needs_followup} turn, reconstructed from Supabase — plus the current turn,
    # appended by evaluate_answer_node. Used by summarize_session_node when the graph ends.
    summary: dict | None  # {overall_feedback, patterns} — set by summarize_session_node
