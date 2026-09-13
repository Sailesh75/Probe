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


def start_session(user_id: UUID, role: str, jd_text: str, resume_text: str) -> tuple[dict, dict]:
    """analyze_profile -> generate the first question, via the start graph.

    Returns (session_row, question_row).
    """
    initial_state: InterviewState = {
        "role": role,
        "profile": SessionProfile(
            jd_text=jd_text,
            resume_text=resume_text,
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
    }
    result = start_graph.invoke(initial_state)

    session_row = repo.create_session(
        user_id=user_id,
        role=role,
        jd_text=jd_text,
        resume_text=resume_text,
        profile=_profile_analysis(result["profile"]),
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
