from app.llm.gemini_client import generate_structured
from app.schemas import GeneratedQuestion, ProfileAnalysis

FRESH_PROMPT_TEMPLATE = """You are conducting a technical/behavioral interview for a {role} role.

Candidate's profile analysis (JD vs. resume):
- Gap areas (JD wants these, resume doesn't clearly show them): {gap_areas}
- Strength areas (resume clearly demonstrates these): {strength_areas}

Ask ONE interview question. Prefer targeting a gap area — that's where a real interviewer would
dig to see if the candidate actually has the skill despite the resume not showing it clearly.
Mix in a strength area sometimes for behavioral depth (e.g. "tell me about a time you...").

Do not repeat any of these already-asked questions: {asked_questions}

Return the question and which specific gap/strength area it targets.
"""

FOLLOWUP_PROMPT_TEMPLATE = """You are conducting a technical/behavioral interview for a {role} role.
The candidate's last answer didn't fully address what you were probing for, and a real
interviewer would press harder here instead of moving on.

TARGET AREA being probed: {target_area}
YOUR PREVIOUS QUESTION: {previous_question}
CANDIDATE'S ANSWER: {previous_answer}
WHY IT FELL SHORT: {feedback}

Ask ONE follow-up question that presses deeper on the same target area, referencing something
specific from their answer (or its absence) rather than repeating the original question verbatim.

Return the follow-up question. target_area should stay {target_area}.
"""


def generate_question(
    role: str, profile: ProfileAnalysis, asked_questions: list[str]
) -> GeneratedQuestion:
    """A fresh question on a new topic, preferring gap areas. Used to start a session and for
    each new (non-followup) question in the multi-question flow."""
    prompt = FRESH_PROMPT_TEMPLATE.format(
        role=role,
        gap_areas=profile.gap_areas or ["(none identified)"],
        strength_areas=profile.strength_areas or ["(none identified)"],
        asked_questions=asked_questions or ["(none yet)"],
    )
    result = generate_structured(prompt, GeneratedQuestion)
    return result  # type: ignore[return-value]


def generate_followup_question(
    role: str, target_area: str, previous_question: str, previous_answer: str, feedback: str
) -> GeneratedQuestion:
    """A probing follow-up on the same target area, used when the evaluator flags
    needs_followup and the per-question follow-up cap hasn't been hit yet."""
    prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
        role=role,
        target_area=target_area,
        previous_question=previous_question,
        previous_answer=previous_answer,
        feedback=feedback,
    )
    result = generate_structured(prompt, GeneratedQuestion)
    return result  # type: ignore[return-value]
