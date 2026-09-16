"""LangGraph nodes for the interview pipeline. Pure state-in/state-out functions —
persistence to Supabase happens in pipeline.py, not here, keeping these nodes testable
without a database and mirroring Phase 1's prompts/db separation.
"""

from typing import Literal

from app.graph.state import MAX_FOLLOWUPS_PER_QUESTION, MAX_QUESTIONS_PER_SESSION, InterviewState
from app.prompts.evaluator import evaluate_answer
from app.prompts.interviewer import generate_followup_question, generate_question
from app.prompts.profile_analyzer import analyze_profile
from app.prompts.summarizer import summarize_session
from app.schemas import ProfileAnalysis


def _profile_from_state(state: InterviewState) -> ProfileAnalysis:
    p = state["profile"]
    return ProfileAnalysis(
        jd_requirements=p["jd_requirements"],
        resume_highlights=p["resume_highlights"],
        gap_areas=p["gap_areas"],
        strength_areas=p["strength_areas"],
    )


def analyze_profile_node(state: InterviewState) -> dict:
    """Node 0: runs once at session start. Grounds the whole session in the JD/resume pairing."""
    result = analyze_profile(state["profile"]["jd_text"], state["profile"]["resume_text"])
    return {
        "profile": {
            **state["profile"],
            "jd_requirements": result.jd_requirements,
            "resume_highlights": result.resume_highlights,
            "gap_areas": result.gap_areas,
            "strength_areas": result.strength_areas,
        }
    }


def generate_question_node(state: InterviewState) -> dict:
    """Node 1: a fresh question (preferring gap_areas) or a targeted follow-up, depending
    on `is_followup` — set by route_after_eval before this node re-runs."""
    company_style_text = state["profile"].get("company_style_text", "")
    if state["is_followup"]:
        question = generate_followup_question(
            role=state["role"],
            target_area=state["current_question_target"],
            previous_question=state["current_question"],
            previous_answer=state["user_answer"],
            feedback=(state["eval_result"] or {}).get("feedback", ""),
            company_style_text=company_style_text,
        )
    else:
        question = generate_question(
            role=state["role"],
            profile=_profile_from_state(state),
            asked_questions=state["asked_questions"],
            company_style_text=company_style_text,
        )

    return {
        "current_question": question.question_text,
        "current_question_target": question.target_area,
        "asked_questions": state["asked_questions"] + [question.question_text],
    }


def evaluate_answer_node(state: InterviewState) -> dict:
    """Node 2: scores the last answer — INTERNAL ONLY, never returned to the client mid-session.
    Also appends this turn to the transcript, which summarize_session_node reads if this turns
    out to be the session's last question."""
    result = evaluate_answer(
        question_text=state["current_question"],
        target_area=state["current_question_target"],
        answer_text=state["user_answer"],
    )
    eval_result = {
        "score": result.score,
        "feedback": result.feedback,
        "needs_followup": result.needs_followup,
    }
    transcript_entry = {
        "question": state["current_question"],
        "target_area": state["current_question_target"],
        "is_followup": state["is_followup"],
        "answer": state["user_answer"],
        **eval_result,
    }
    return {
        "eval_result": eval_result,
        "transcript": state["transcript"] + [transcript_entry],
    }


def prepare_followup(state: InterviewState) -> dict:
    """Bumps the follow-up counter before generate_question_node runs in follow-up mode.
    Split out from route_after_eval since LangGraph's conditional-edge routers can only pick
    the next node, not mutate state — that's this node's job."""
    return {"is_followup": True, "followup_count": state["followup_count"] + 1}


def prepare_next_question(state: InterviewState) -> dict:
    """Resets the follow-up counter and advances the question count before
    generate_question_node runs in fresh-question mode."""
    return {
        "is_followup": False,
        "followup_count": 0,
        "questions_asked": state["questions_asked"] + 1,
    }


def mark_has_next_question(state: InterviewState) -> dict:
    return {"has_next": True}


def mark_interview_complete(state: InterviewState) -> dict:
    return {"has_next": False}


def summarize_session_node(state: InterviewState) -> dict:
    """Node 4: runs once, when route_after_eval decides to end the session. This is the first
    point anywhere in the flow that scores/feedback are revealed — everything before this was
    computed (evaluate_answer_node) and stored but withheld from the client."""
    result = summarize_session(role=state["role"], transcript=state["transcript"])
    overall_score = sum(t["score"] for t in state["transcript"]) / len(state["transcript"])
    return {
        "summary": {
            "overall_score": round(overall_score, 2),
            "overall_feedback": result.overall_feedback,
            "patterns": [p.model_dump() for p in result.patterns],
        }
    }


def route_after_eval(state: InterviewState) -> Literal["followup", "next_question", "end"]:
    """Node 3: the real conditional branch — depends on the evaluator's actual output, not a
    scripted turn count. This is what the plan calls out as the genuine multi-agent decision."""
    eval_result = state["eval_result"] or {}

    if eval_result.get("needs_followup") and state["followup_count"] < MAX_FOLLOWUPS_PER_QUESTION:
        return "followup"
    if state["questions_asked"] < MAX_QUESTIONS_PER_SESSION:
        return "next_question"
    return "end"
