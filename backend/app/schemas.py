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
