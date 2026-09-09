"""Orchestrates prompts + persistence for Phase 1's single-question flow.

No LangGraph yet (that's Phase 3) — this is the plain-function pipeline the roadmap
calls for, structured so it's a straightforward lift into graph/nodes.py later:
analyze_profile -> generate_question -> [user answers] -> evaluate_answer.
"""

from uuid import UUID

from app.db import repo
from app.prompts.evaluator import evaluate_answer
from app.prompts.interviewer import generate_question
from app.prompts.profile_analyzer import analyze_profile
from app.schemas import EvaluationResult


def start_session(user_id: UUID, role: str, jd_text: str, resume_text: str) -> tuple[dict, dict]:
    """analyze_profile -> store session -> generate one question -> store it.

    Returns (session_row, question_row).
    """
    profile = analyze_profile(jd_text, resume_text)
    session_row = repo.create_session(user_id, role, jd_text, resume_text, profile)
    question = generate_question(role, profile, asked_questions=[])
    question_row = repo.create_question(
        session_id=session_row["id"],
        question_text=question.question_text,
        target_area=question.target_area,
        order_index=0,
    )
    return session_row, question_row


def submit_answer(
    question_id: UUID, answer_text: str, user_id: UUID, session_id: UUID
) -> EvaluationResult:
    """evaluate_answer -> store the answer with its score/feedback.

    Returns the EvaluationResult so callers (tests, demo scripts) can inspect it —
    but the API router must NOT forward score/feedback/needs_followup to the client.
    That's the "no live grading" contract from the plan, enforced at the API boundary.

    Also confirms the question actually belongs to `session_id`, and that session
    actually belongs to `user_id` — otherwise anyone holding a question_id could answer
    into someone else's session (or the wrong session in their own URL).
    """
    question_row = repo.get_question(question_id)
    if question_row is None or question_row["session_id"] != str(session_id):
        raise ValueError(f"No question {question_id} found in session {session_id}")

    session_row = repo.get_session(session_id)
    if session_row is None or session_row["user_id"] != str(user_id):
        raise PermissionError("This session does not belong to the current user")

    eval_result = evaluate_answer(
        question_text=question_row["question_text"],
        target_area=question_row["target_area"],
        answer_text=answer_text,
    )
    repo.create_answer(
        question_id=question_id,
        answer_text=answer_text,
        score=eval_result.score,
        feedback=eval_result.feedback,
        needs_followup=eval_result.needs_followup,
    )
    return eval_result
