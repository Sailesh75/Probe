"""Persistence layer for Phase 1: sessions, questions, answers.

Kept as plain functions over the Supabase table API (no ORM) since Phase 1 doesn't
need anything fancier yet. The backend uses the service_role key, so it bypasses the
RLS policy in db/schema.sql and is responsible for scoping by user_id itself.
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
    session_id: UUID, question_text: str, target_area: str, order_index: int
) -> dict[str, Any]:
    row = {
        "session_id": str(session_id),
        "question_text": question_text,
        "target_area": target_area,
        "is_followup": False,
        "order_index": order_index,
    }
    result = get_supabase().table("questions").insert(row).execute()
    return result.data[0]


def get_question(question_id: UUID) -> dict[str, Any] | None:
    result = get_supabase().table("questions").select("*").eq("id", str(question_id)).execute()
    return result.data[0] if result.data else None


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
