"""Orchestrates the LangGraph pipeline + persistence for the interview flow.

Each HTTP request re-hydrates just enough InterviewState from Supabase to run one graph
invocation (see app/graph), then persists whatever the graph produced. There's no long-lived
graph process or checkpointer spanning requests — Supabase's sessions/questions/answers
tables are the durable state; the graph is the branching logic layered on top of it.
"""

from uuid import UUID

from app.db import repo
from app.graph.graph import start_graph, turn_graph
from app.graph.state import InterviewState, SessionProfile
from app.schemas import ProfileAnalysis


def _profile_analysis(profile: SessionProfile) -> ProfileAnalysis:
    return ProfileAnalysis(
        jd_requirements=profile["jd_requirements"],
        resume_highlights=profile["resume_highlights"],
        gap_areas=profile["gap_areas"],
        strength_areas=profile["strength_areas"],
    )


def _trailing_followup_count(questions: list[dict]) -> int:
    """How many consecutive follow-ups sit at the end of the question list — i.e. how many
    follow-ups have already been asked for the question currently being answered."""
    count = 0
    for q in reversed(questions):
        if not q["is_followup"]:
            break
        count += 1
    return count


def start_session(
    user_id: UUID, role: str, jd_text: str, resume_text: str, company_style_text: str = ""
) -> tuple[dict, dict]:
    """analyze_profile -> generate the first question, via the start graph.

    Returns (session_row, question_row).
    """
    initial_state: InterviewState = {
        "role": role,
        "profile": SessionProfile(
            jd_text=jd_text,
            resume_text=resume_text,
            company_style_text=company_style_text,
            jd_requirements=[],
            resume_highlights=[],
            gap_areas=[],
            strength_areas=[],
        ),
        "asked_questions": [],
        "current_question": "",
        "current_question_target": "",
        "is_followup": False,
        "followup_count": 0,
        "questions_asked": 1,  # this first question counts against the session's budget
        "user_answer": "",
        "eval_result": None,
        "has_next": True,
        "transcript": [],
        "summary": None,
    }
    result = start_graph.invoke(initial_state)

    session_row = repo.create_session(
        user_id=user_id,
        role=role,
        jd_text=jd_text,
        resume_text=resume_text,
        profile=_profile_analysis(result["profile"]),
        company_style_text=company_style_text,
    )
    question_row = repo.create_question(
        session_id=session_row["id"],
        question_text=result["current_question"],
        target_area=result["current_question_target"],
        order_index=0,
    )
    return session_row, question_row


def submit_answer(
    question_id: UUID, answer_text: str, user_id: UUID, session_id: UUID
) -> dict:
    """evaluate_answer -> route_after_eval -> maybe generate the next question, via the turn
    graph. Also confirms the question belongs to `session_id`, and that session belongs to
    `user_id` — otherwise anyone holding a question_id could answer into someone else's session.

    Returns {"has_next": bool}. Callers (the API router) must not forward score/feedback —
    that's the "no live grading" contract enforced at the API boundary, not here.
    """
    question_row = repo.get_question(question_id)
    if question_row is None or question_row["session_id"] != str(session_id):
        raise ValueError(f"No question {question_id} found in session {session_id}")

    session_row = repo.get_session(session_id)
    if session_row is None or session_row["user_id"] != str(user_id):
        raise PermissionError("This session does not belong to the current user")

    all_questions = repo.get_questions_for_session(session_id)
    state: InterviewState = {
        "role": session_row["role"],
        "profile": SessionProfile(
            jd_text=session_row["jd_text"],
            resume_text=session_row["resume_text"],
            company_style_text=session_row.get("company_style_text") or "",
            jd_requirements=session_row["jd_requirements"] or [],
            resume_highlights=session_row["resume_highlights"] or [],
            gap_areas=session_row["gap_areas"] or [],
            strength_areas=session_row["strength_areas"] or [],
        ),
        "asked_questions": [q["question_text"] for q in all_questions],
        "current_question": question_row["question_text"],
        "current_question_target": question_row["target_area"],
        "is_followup": question_row["is_followup"],
        "followup_count": _trailing_followup_count(all_questions),
        "questions_asked": sum(1 for q in all_questions if not q["is_followup"]),
        "user_answer": answer_text,
        "eval_result": None,
        "has_next": False,
        "transcript": repo.get_transcript_for_session(session_id),
        "summary": None,
    }

    result = turn_graph.invoke(state)

    eval_result = result["eval_result"]
    repo.create_answer(
        question_id=question_id,
        answer_text=answer_text,
        score=eval_result["score"],
        feedback=eval_result["feedback"],
        needs_followup=eval_result["needs_followup"],
    )

    if result["has_next"]:
        repo.create_question(
            session_id=session_id,
            question_text=result["current_question"],
            target_area=result["current_question_target"],
            order_index=len(all_questions),
            is_followup=result["is_followup"],
            parent_question_id=question_id if result["is_followup"] else None,
        )
    else:
        # route_after_eval picked "end" -> summarize_session_node already ran.
        summary = result["summary"]
        repo.create_session_summary(
            session_id=session_id,
            overall_score=summary["overall_score"],
            overall_feedback=summary["overall_feedback"],
            patterns=summary["patterns"],
        )
        repo.update_session_status(session_id, "completed")

    return {"has_next": result["has_next"]}


def get_next_question(session_id: UUID, user_id: UUID) -> dict:
    """The most recent question in the session, if it hasn't been answered yet.

    Backs GET /sessions/{id}/next-question — also what lets the frontend resume a session
    after a page refresh, since the pending question now lives in Supabase, not router state.
    """
    session_row = repo.get_session(session_id)
    if session_row is None or session_row["user_id"] != str(user_id):
        raise PermissionError("This session does not belong to the current user")

    all_questions = repo.get_questions_for_session(session_id)
    if not all_questions:
        raise ValueError(f"No questions found for session {session_id}")

    latest = all_questions[-1]
    if repo.get_answer_for_question(latest["id"]) is not None:
        raise ValueError("No pending question — the interview is complete")

    return latest


def get_session_summary(session_id: UUID, user_id: UUID) -> dict:
    """The results screen's data: overall score, recurring patterns, and the full
    per-question breakdown. Only available once summarize_session_node has actually run —
    i.e. the interview reached a natural end, not merely "the latest question is answered".
    """
    session_row = repo.get_session(session_id)
    if session_row is None or session_row["user_id"] != str(user_id):
        raise PermissionError("This session does not belong to the current user")

    summary_row = repo.get_session_summary(session_id)
    if summary_row is None:
        raise ValueError("No summary yet — this interview isn't complete")

    return {
        "overall_score": summary_row["overall_score"],
        "overall_feedback": summary_row["patterns"]["overall_feedback"],
        "patterns": summary_row["patterns"]["issues"],
        "questions": repo.get_transcript_for_session(session_id),
    }


def list_sessions(user_id: UUID) -> list[dict]:
    """Past sessions for the history screen — no score/feedback here, just enough to list
    and link into each one's results (once completed)."""
    sessions = repo.get_sessions_for_user(user_id)
    return [
        {
            "session_id": s["id"],
            "role": s["role"],
            "status": s["status"],
            "created_at": s["created_at"],
        }
        for s in sessions
    ]


def get_score_trend(user_id: UUID) -> dict:
    """Score trend across a user's completed sessions — the plan's section 6 "improvement
    over time" hook. Simplified from the plan's sketch (which groups by a behavioral/
    technical/system-design category): that needs a question-classification step nothing
    upstream produces yet, so this groups by role instead, which the data already has.
    """
    sessions = repo.get_completed_sessions_with_summary(user_id)
    scores = [s["overall_score"] for s in sessions]

    if not scores:
        return {"sessions": [], "trend": "not_enough_data", "avg_score": None}

    trend = "not_enough_data"
    if len(scores) >= 2:
        trend = "improving" if scores[-1] > scores[0] else "flat_or_declining"

    return {
        "sessions": sessions,
        "trend": trend,
        "avg_score": round(sum(scores) / len(scores), 2),
    }
