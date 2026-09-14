"""Persistence layer: sessions, questions, answers.

Kept as plain functions over the Supabase table API (no ORM) — Phase 1 didn't need
anything fancier, and Phase 3 just adds follow-up chains within the same schema. The
backend uses the service_role key, so it bypasses the RLS policy in db/schema.sql and
is responsible for scoping by user_id itself.
"""

from typing import Any
from uuid import UUID

from app.db.supabase_client import get_supabase
from app.schemas import ProfileAnalysis


def create_session(
    user_id: UUID, role: str, jd_text: str, resume_text: str, profile: ProfileAnalysis
) -> dict[str, Any]:
    row = {
        "user_id": str(user_id),
        "role": role,
        "jd_text": jd_text,
        "resume_text": resume_text,
        "jd_requirements": profile.jd_requirements,
        "resume_highlights": profile.resume_highlights,
        "gap_areas": profile.gap_areas,
        "strength_areas": profile.strength_areas,
    }
    result = get_supabase().table("sessions").insert(row).execute()
    return result.data[0]


def get_session(session_id: UUID) -> dict[str, Any] | None:
    result = get_supabase().table("sessions").select("*").eq("id", str(session_id)).execute()
    return result.data[0] if result.data else None


def create_question(
    session_id: UUID,
    question_text: str,
    target_area: str,
    order_index: int,
    is_followup: bool = False,
    parent_question_id: UUID | None = None,
) -> dict[str, Any]:
    row = {
        "session_id": str(session_id),
        "question_text": question_text,
        "target_area": target_area,
        "is_followup": is_followup,
        "parent_question_id": str(parent_question_id) if parent_question_id else None,
        "order_index": order_index,
    }
    result = get_supabase().table("questions").insert(row).execute()
    return result.data[0]


def get_question(question_id: UUID) -> dict[str, Any] | None:
    result = get_supabase().table("questions").select("*").eq("id", str(question_id)).execute()
    return result.data[0] if result.data else None


def get_questions_for_session(session_id: UUID) -> list[dict[str, Any]]:
    result = (
        get_supabase()
        .table("questions")
        .select("*")
        .eq("session_id", str(session_id))
        .order("order_index")
        .execute()
    )
    return result.data


def create_answer(
    question_id: UUID, answer_text: str, score: int, feedback: str, needs_followup: bool
) -> dict[str, Any]:
    row = {
        "question_id": str(question_id),
        "answer_text": answer_text,
        "score": score,
        "feedback": feedback,
        "needs_followup": needs_followup,
    }
    result = get_supabase().table("answers").insert(row).execute()
    return result.data[0]


def get_answer_for_question(question_id: UUID) -> dict[str, Any] | None:
    result = (
        get_supabase().table("answers").select("*").eq("question_id", str(question_id)).execute()
    )
    return result.data[0] if result.data else None


def get_transcript_for_session(session_id: UUID) -> list[dict[str, Any]]:
    """Every already-answered question in the session, oldest first, flattened into the shape
    summarize_session_node expects. One query (questions embedding their answers) instead of
    N+1. Only includes answered questions — the current in-flight turn isn't in here yet;
    evaluate_answer_node appends it itself before summarize_session_node runs."""
    result = (
        get_supabase()
        .table("questions")
        .select("*, answers(*)")
        .eq("session_id", str(session_id))
        .order("order_index")
        .execute()
    )
    transcript = []
    for q in result.data:
        answers = q.get("answers") or []
        if not answers:
            continue
        a = answers[0]
        transcript.append(
            {
                "question": q["question_text"],
                "target_area": q["target_area"],
                "is_followup": q["is_followup"],
                "answer": a["answer_text"],
                "score": a["score"],
                "feedback": a["feedback"],
                "needs_followup": a["needs_followup"],
            }
        )
    return transcript


def update_session_status(session_id: UUID, status: str) -> None:
    get_supabase().table("sessions").update({"status": status}).eq("id", str(session_id)).execute()


def create_session_summary(
    session_id: UUID, overall_score: float, overall_feedback: str, patterns: list[dict]
) -> dict[str, Any]:
    # `session_summaries.patterns` is jsonb with no fixed shape in the schema, so
    # overall_feedback rides along inside it — avoids an ALTER TABLE for one extra string.
    row = {
        "session_id": str(session_id),
        "overall_score": overall_score,
        "patterns": {"overall_feedback": overall_feedback, "issues": patterns},
    }
    result = get_supabase().table("session_summaries").insert(row).execute()
    return result.data[0]


def get_session_summary(session_id: UUID) -> dict[str, Any] | None:
    result = (
        get_supabase()
        .table("session_summaries")
        .select("*")
        .eq("session_id", str(session_id))
        .execute()
    )
    return result.data[0] if result.data else None


def get_sessions_for_user(user_id: UUID) -> list[dict[str, Any]]:
    result = (
        get_supabase()
        .table("sessions")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def get_completed_sessions_with_summary(user_id: UUID) -> list[dict[str, Any]]:
    """Completed sessions with their score, oldest first — the raw material for a trend
    line. One query (sessions embedding session_summaries) instead of N+1."""
    result = (
        get_supabase()
        .table("sessions")
        .select("id, role, created_at, session_summaries(overall_score)")
        .eq("user_id", str(user_id))
        .eq("status", "completed")
        .order("created_at")
        .execute()
    )
    trend = []
    for s in result.data:
        summaries = s.get("session_summaries") or []
        if not summaries:
            continue
        trend.append(
            {
                "session_id": s["id"],
                "role": s["role"],
                "created_at": s["created_at"],
                "overall_score": summaries[0]["overall_score"],
            }
        )
    return trend
