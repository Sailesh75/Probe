from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import pipeline
from app.auth import get_current_user_id

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    role: str
    jd_text: str
    resume_text: str


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
        )
    except Exception as exc:  # LLM or DB failure
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
    """Evaluates and stores the answer. Deliberately returns only {recorded, has_next} —
    never the score/feedback the evaluator just produced. Phase 1 is single-question,
    so has_next is always False; Phase 3 wires this up to the follow-up/next-question routing.
    """
    try:
        pipeline.submit_answer(
            question_id=body.question_id,
            answer_text=body.answer_text,
            user_id=user_id,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:  # LLM or DB failure
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SubmitAnswerResponse(recorded=True, has_next=False)
