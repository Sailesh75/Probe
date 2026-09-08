from app.llm.gemini_client import generate_structured
from app.schemas import GeneratedQuestion, ProfileAnalysis

PROMPT_TEMPLATE = """You are conducting a technical/behavioral interview for a {role} role.

Candidate's profile analysis (JD vs. resume):
- Gap areas (JD wants these, resume doesn't clearly show them): {gap_areas}
- Strength areas (resume clearly demonstrates these): {strength_areas}

Ask ONE interview question. Prefer targeting a gap area — that's where a real interviewer would
dig to see if the candidate actually has the skill despite the resume not showing it clearly.
Mix in a strength area sometimes for behavioral depth (e.g. "tell me about a time you...").

Do not repeat any of these already-asked questions: {asked_questions}

Return the question and which specific gap/strength area it targets.
"""


def generate_question(
    role: str, profile: ProfileAnalysis, asked_questions: list[str]
) -> GeneratedQuestion:
    prompt = PROMPT_TEMPLATE.format(
        role=role,
        gap_areas=profile.gap_areas or ["(none identified)"],
        strength_areas=profile.strength_areas or ["(none identified)"],
        asked_questions=asked_questions or ["(none yet)"],
    )
    result = generate_structured(prompt, GeneratedQuestion)
    return result  # type: ignore[return-value]
