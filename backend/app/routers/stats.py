from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import pipeline
from app.auth import get_current_user_id

router = APIRouter(prefix="/stats", tags=["stats"])


class TrendPoint(BaseModel):
    session_id: UUID
    role: str
    created_at: str
    overall_score: float


class TrendResponse(BaseModel):
    sessions: list[TrendPoint]
    trend: str  # "improving" | "flat_or_declining" | "not_enough_data"
    avg_score: float | None


@router.get("/trends", response_model=TrendResponse)
def get_trends(user_id: UUID = Depends(get_current_user_id)) -> TrendResponse:
    """Score trend across the user's completed sessions — the plan's section 6
    "improvement over time" hook. Aggregate only; no per-question detail here."""
    data = pipeline.get_score_trend(user_id=user_id)
    return TrendResponse(
        sessions=[TrendPoint(**s) for s in data["sessions"]],
        trend=data["trend"],
        avg_score=data["avg_score"],
    )
