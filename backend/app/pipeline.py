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


def submit_answer(question_id: UUID, answer_text: str) -> EvaluationResult:
    """evaluate_answer -> store the answer with its score/feedback.

    Returns the EvaluationResult so callers (tests, demo scripts) can inspect it —
    but the API router must NOT forward score/feedback/needs_followup to the client.
    That's the "no live grading" contract from the plan, enforced at the API boundary.
    """
    question_row = repo.get_question(question_id)
    if question_row is None:
        raise ValueError(f"No question found with id {question_id}")

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
