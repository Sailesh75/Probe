import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import pipeline
from app.auth import get_current_user_id
from app.llm.gemini_client import GeminiUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    role: str
    jd_text: str
    resume_text: str
    company_style_text: str = ""  # optional: pasted real questions (e.g. Glassdoor) to mimic


class CreateSessionResponse(BaseModel):
    session_id: UUID
    question_id: UUID
    question_text: str


class SubmitAnswerRequest(BaseModel):
    question_id: UUID
    answer_text: str


class SubmitAnswerResponse(BaseModel):
    recorded: bool
    has_next: bool


class NextQuestionResponse(BaseModel):
    question_id: UUID
    question_text: str
    is_followup: bool


class QuestionBreakdown(BaseModel):
    question_text: str
    is_followup: bool
    answer_text: str
    score: int
    feedback: str


class WeaknessPatternResponse(BaseModel):
    issue: str
    count: int


class SessionSummaryResponse(BaseModel):
    overall_score: float
    overall_feedback: str
    patterns: list[WeaknessPatternResponse]
    questions: list[QuestionBreakdown]


class SessionListItem(BaseModel):
    session_id: UUID
    role: str
    status: str
    created_at: datetime


@router.post("", response_model=CreateSessionResponse)
def create_session(
    body: CreateSessionRequest, user_id: UUID = Depends(get_current_user_id)
) -> CreateSessionResponse:
    """Runs analyze_profile, stores the session, generates + stores one question.

    Returns only the question — never the score/feedback contract applies from
    the very first response. user_id comes from the verified auth token, never
    from the request body — a client can't create sessions under someone else's id.
    """
    try:
        session_row, question_row = pipeline.start_session(
            user_id=user_id,
            role=body.role,
            jd_text=body.jd_text,
            resume_text=body.resume_text,
            company_style_text=body.company_style_text,
        )
    except GeminiUnavailableError as exc:
        logger.warning("create_session: Gemini unavailable for user %s: %s", user_id, exc)
        raise HTTPException(status_code=503, detail=exc.user_message()) from exc
    except Exception as exc:  # DB failure or other bug
        logger.exception("create_session failed for user %s", user_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return CreateSessionResponse(
        session_id=session_row["id"],
        question_id=question_row["id"],
        question_text=question_row["question_text"],
    )


@router.post("/{session_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(
    session_id: UUID, body: SubmitAnswerRequest, user_id: UUID = Depends(get_current_user_id)
) -> SubmitAnswerResponse:
    """Evaluates and stores the answer, then runs route_after_eval — the genuine branching
    decision (follow up / next question / end) — and stores the next question if there is one.

    Deliberately returns only {recorded, has_next} — never the score/feedback the evaluator
    just produced, and never the next question's text either (fetch that via
    GET /{session_id}/next-question). That's the "no live grading" contract from the plan,
    enforced at the API boundary.
    """
    try:
        result = pipeline.submit_answer(
            question_id=body.question_id,
            answer_text=body.answer_text,
            user_id=user_id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GeminiUnavailableError as exc:
        logger.warning("submit_answer: Gemini unavailable for session %s: %s", session_id, exc)
        raise HTTPException(status_code=503, detail=exc.user_message()) from exc
    except Exception as exc:  # DB failure or other bug
        logger.exception("submit_answer failed for session %s", session_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SubmitAnswerResponse(recorded=True, has_next=result["has_next"])


@router.get("/{session_id}/next-question", response_model=NextQuestionResponse)
def next_question(
    session_id: UUID, user_id: UUID = Depends(get_current_user_id)
) -> NextQuestionResponse:
    """The current pending (unanswered) question for this session. Also what lets the
    frontend resume a session after a page refresh — the pending question lives in Supabase,
    not in frontend router state.
    """
    try:
        question_row = pipeline.get_next_question(session_id=session_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return NextQuestionResponse(
        question_id=question_row["id"],
        question_text=question_row["question_text"],
        is_followup=question_row["is_followup"],
    )


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
def get_summary(
    session_id: UUID, user_id: UUID = Depends(get_current_user_id)
) -> SessionSummaryResponse:
    """The results screen: overall score, recurring patterns, and the full per-question
    breakdown — the first point anywhere in the API that score/feedback are ever returned.
    Only available once the interview has actually ended (summarize_session_node ran).
    """
    try:
        data = pipeline.get_session_summary(session_id=session_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return SessionSummaryResponse(
        overall_score=data["overall_score"],
        overall_feedback=data["overall_feedback"],
        patterns=[WeaknessPatternResponse(**p) for p in data["patterns"]],
        questions=[
            QuestionBreakdown(
                question_text=q["question"],
                is_followup=q["is_followup"],
                answer_text=q["answer"],
                score=q["score"],
                feedback=q["feedback"],
            )
            for q in data["questions"]
        ],
    )


@router.get("", response_model=list[SessionListItem])
def list_sessions(user_id: UUID = Depends(get_current_user_id)) -> list[SessionListItem]:
    """Past sessions for the history screen — no score/feedback, just enough to list and
    link into each one's results once completed."""
    sessions = pipeline.list_sessions(user_id=user_id)
    return [SessionListItem(**s) for s in sessions]
