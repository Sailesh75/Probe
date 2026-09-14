"""Structured shapes shared between the LLM prompt functions and the API layer.

These double as the Gemini `response_schema` (forces JSON that matches the shape)
and as the FastAPI response models.
"""

from pydantic import BaseModel, Field


class ProfileAnalysis(BaseModel):
    jd_requirements: list[str] = Field(
        description="Key skills/responsibilities extracted from the job description."
    )
    resume_highlights: list[str] = Field(
        description="Relevant experience/claims extracted from the resume."
    )
    gap_areas: list[str] = Field(
        description="Things the JD wants that the resume doesn't clearly show."
    )
    strength_areas: list[str] = Field(
        description="Things the resume shows strong, relevant experience in."
    )


class GeneratedQuestion(BaseModel):
    question_text: str
    target_area: str = Field(
        description="The gap_area or strength_area this question is probing."
    )


class EvaluationResult(BaseModel):
    score: int = Field(ge=1, le=5, description="1 (weak) to 5 (excellent).")
    feedback: str = Field(description="Specific, actionable feedback on the answer.")
    needs_followup: bool = Field(
        description="True if the answer was vague/incomplete and deserves a probing follow-up."
    )


class WeaknessPattern(BaseModel):
    issue: str = Field(
        description="A specific, recurring weakness observed across MULTIPLE answers — "
        "not a one-off restated from a single question's feedback."
    )
    count: int = Field(description="How many answers in the transcript exhibited this issue.")


class SessionSummary(BaseModel):
    overall_feedback: str = Field(
        description="A 2-4 sentence qualitative summary of the candidate's overall performance, "
        "referencing specifics from the transcript."
    )
    patterns: list[WeaknessPattern] = Field(
        description="Recurring weaknesses across the session. Empty if nothing recurred "
        "(a single weak answer isn't a pattern)."
    )
