from app.llm.gemini_client import generate_structured
from app.schemas import EvaluationResult

PROMPT_TEMPLATE = """You are an interview evaluator. Score the candidate's answer to the question
below. This scoring is INTERNAL ONLY — the candidate will never see it during the interview,
so be honest and specific rather than encouraging.

QUESTION: {question_text}
TARGET AREA (what this question was meant to probe): {target_area}

CANDIDATE'S ANSWER:
---
{answer_text}
---

Score 1-5 (1 = did not address the question / no substance, 5 = clear, specific, well-structured,
directly answers what was asked). Give concrete feedback tied to specifics in the answer, not
generic advice. Set needs_followup=true only if the answer is vague, incomplete, or dodges the
target area in a way a real interviewer would want to press on.
"""


def evaluate_answer(question_text: str, target_area: str, answer_text: str) -> EvaluationResult:
    prompt = PROMPT_TEMPLATE.format(
        question_text=question_text, target_area=target_area, answer_text=answer_text
    )
    result = generate_structured(prompt, EvaluationResult)
    return result  # type: ignore[return-value]
