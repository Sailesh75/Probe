import random

from app.llm.gemini_client import generate_structured
from app.schemas import GeneratedQuestion, ProfileAnalysis

FRESH_PROMPT_TEMPLATE = """You are conducting a technical interview for a {role} role.

Candidate's profile analysis (JD vs. resume):
- Gap areas (JD wants these, resume doesn't clearly show them): {gap_areas}
- Strength areas (resume clearly demonstrates these): {strength_areas}
{company_style_block}
Ask ONE technical or role-specific question. Prefer targeting a gap area — that's where a real
interviewer would dig to see if the candidate actually has the skill despite the resume not
showing it clearly. Mix in a strength area sometimes to test real depth. Behavioral questions
("tell me about a time you...") are asked separately — don't ask one here.

Do not repeat any of these already-asked questions: {asked_questions}

Return the question and which specific gap/strength area it targets.
"""

BEHAVIORAL_PROMPT_TEMPLATE = """You are conducting an interview for a {role} role, and it's time
for a behavioral or scenario-based question — the kind every real interview loop includes,
whether or not the job description mentions it.

Job description (for context on the company, team, and day-to-day work):
---
{jd_text}
---
{company_style_block}
THEME for this question: {theme}

Ask ONE behavioral question on that theme: either a past-experience question ("Tell me about a
time...") or a hypothetical scenario ("Imagine you're... what would you do?"), whichever fits the
theme better. Ground it in this company or role when the JD gives you something to work with
(its product, customers, pace, values); otherwise a well-phrased general question is fine. Avoid
the most clichéd wording, and don't ask anything close to these already-asked questions:
{asked_questions}

Return the question, and as target_area a short (2-5 word) name for the competency it probes.
"""

# Picked at random per question so behavioral questions don't converge on the same "tell me
# about a conflict" every session — left to itself, the model repeats a handful of favorites.
BEHAVIORAL_THEMES = [
    "handling conflict or disagreement with a teammate",
    "disagreeing with a manager or senior stakeholder",
    "a failure or mistake and what was learned",
    "working under a tight deadline",
    "prioritizing competing demands",
    "making a decision with incomplete information",
    "taking ownership beyond your assigned scope",
    "receiving and acting on difficult feedback",
    "learning something new quickly",
    "influencing others without formal authority",
    "dealing with an unhappy customer or user",
    "explaining something complex to a non-expert",
    "a project you're most proud of and your specific role in it",
    "adapting when requirements changed mid-project",
    "why this company and this role specifically",
    "helping a struggling teammate",
    "pushing back on a bad idea or unrealistic request",
    "balancing quality against speed",
]

FOLLOWUP_PROMPT_TEMPLATE ="""You are conducting a technical/behavioral interview for a {role} role.
The candidate's last answer didn't fully address what you were probing for, and a real
interviewer would press harder here instead of moving on.
{company_style_block}
TARGET AREA being probed: {target_area}
YOUR PREVIOUS QUESTION: {previous_question}
CANDIDATE'S ANSWER: {previous_answer}
WHY IT FELL SHORT: {feedback}

Ask ONE follow-up question that presses deeper on the same target area, referencing something
specific from their answer (or its absence) rather than repeating the original question verbatim.

Return the follow-up question. target_area should stay {target_area}.
"""

_COMPANY_STYLE_BLOCK = """
The candidate is prepping for a specific company. Here are real questions previously asked in
that company's interviews:
---
{company_style_text}
---
Match this company's tone, phrasing style, and the areas it tends to emphasize — but don't just
reuse one of these questions verbatim, and don't let it override targeting the gap/target areas
above; blend the two; the company's *style*, not its literal question list, is what to copy.
"""


def _company_style_block(company_style_text: str) -> str:
    if not company_style_text.strip():
        return ""
    return _COMPANY_STYLE_BLOCK.format(company_style_text=company_style_text)


def generate_question(
    role: str,
    profile: ProfileAnalysis,
    asked_questions: list[str],
    company_style_text: str = "",
) -> GeneratedQuestion:
    """A fresh question on a new topic, preferring gap areas. Used to start a session and for
    each new (non-followup) question in the multi-question flow."""
    prompt = FRESH_PROMPT_TEMPLATE.format(
        role=role,
        gap_areas=profile.gap_areas or ["(none identified)"],
        strength_areas=profile.strength_areas or ["(none identified)"],
        asked_questions=asked_questions or ["(none yet)"],
        company_style_block=_company_style_block(company_style_text),
    )
    result = generate_structured(prompt, GeneratedQuestion)
    return result  # type: ignore[return-value]


def generate_behavioral_question(
    role: str,
    jd_text: str,
    asked_questions: list[str],
    company_style_text: str = "",
) -> GeneratedQuestion:
    """A behavioral/scenario question on a randomly chosen theme, grounded in the company
    from the JD where possible. target_area comes back as just the competency name; the
    caller adds BEHAVIORAL_TARGET_PREFIX."""
    prompt = BEHAVIORAL_PROMPT_TEMPLATE.format(
        role=role,
        jd_text=jd_text[:4000],
        theme=random.choice(BEHAVIORAL_THEMES),
        asked_questions=asked_questions or ["(none yet)"],
        company_style_block=_company_style_block(company_style_text),
    )
    result = generate_structured(prompt, GeneratedQuestion)
    return result  # type: ignore[return-value]


def generate_followup_question(
    role: str,
    target_area: str,
    previous_question: str,
    previous_answer: str,
    feedback: str,
    company_style_text: str = "",
) -> GeneratedQuestion:
    """A probing follow-up on the same target area, used when the evaluator flags
    needs_followup and the per-question follow-up cap hasn't been hit yet."""
    prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
        role=role,
        target_area=target_area,
        previous_question=previous_question,
        previous_answer=previous_answer,
        feedback=feedback,
        company_style_block=_company_style_block(company_style_text),
    )
    result = generate_structured(prompt, GeneratedQuestion)
    return result  # type: ignore[return-value]
