from app.llm.gemini_client import generate_structured
from app.schemas import ProfileAnalysis

PROMPT_TEMPLATE = """You are an expert technical recruiter and hiring manager.
Compare the following job description and candidate resume.

JOB DESCRIPTION:
---
{jd_text}
---

RESUME:
---
{resume_text}
---

Analyze this pairing and return:
- jd_requirements: the key skills/responsibilities the JD is actually asking for (be specific,
  not generic — e.g. "3+ years building production ETL pipelines" not just "data engineering").
- resume_highlights: the relevant experience/claims in the resume that speak to those requirements.
- gap_areas: requirements the JD emphasizes that the resume does NOT clearly demonstrate.
  These are the areas a good interviewer would probe hardest.
- strength_areas: requirements the resume clearly and strongly demonstrates.

Every item in gap_areas and strength_areas must trace back to something in jd_requirements —
don't invent requirements the JD doesn't mention.
"""


def analyze_profile(jd_text: str, resume_text: str) -> ProfileAnalysis:
    """Runs once at session start. Grounds question selection in the actual JD/resume pairing
    instead of asking generic interview questions."""
    prompt = PROMPT_TEMPLATE.format(jd_text=jd_text, resume_text=resume_text)
    result = generate_structured(prompt, ProfileAnalysis)
    return result  # type: ignore[return-value]
