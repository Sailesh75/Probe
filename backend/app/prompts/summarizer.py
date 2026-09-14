from app.llm.gemini_client import generate_structured
from app.schemas import SessionSummary

PROMPT_TEMPLATE = """You are reviewing a completed mock interview for a {role} role. Below is
the full transcript: every question asked, the candidate's answer, and the internal score/
feedback already given for each (1-5).

TRANSCRIPT:
{transcript_text}

Identify recurring patterns across MULTIPLE answers — not a repeat of one question's feedback.
Look for things like: consistently vague answers, missing the STAR method's Result step,
jumping to solutions without clarifying requirements first, claiming a skill on the resume that
didn't hold up under a follow-up, strong technical depth but weak communication, etc. Only
include a pattern if it shows up in 2 or more answers — a single weak answer isn't a pattern.

Also write overall_feedback: a short, honest 2-4 sentence summary of how the candidate did,
referencing specifics from the transcript rather than generic encouragement.
"""


def _format_transcript(transcript: list[dict]) -> str:
    lines = []
    for i, turn in enumerate(transcript, start=1):
        tag = " (follow-up)" if turn["is_followup"] else ""
        lines.append(
            f"Q{i}{tag} [{turn['target_area']}]: {turn['question']}\n"
            f"A{i}: {turn['answer']}\n"
            f"Score: {turn['score']}/5 — {turn['feedback']}\n"
        )
    return "\n".join(lines)


def summarize_session(role: str, transcript: list[dict]) -> SessionSummary:
    """Node 4: runs once, when route_after_eval decides to end the session. This is the first
    point anywhere in the flow that scores/feedback are revealed — everything before this was
    computed and stored but withheld from the client."""
    prompt = PROMPT_TEMPLATE.format(role=role, transcript_text=_format_transcript(transcript))
    result = generate_structured(prompt, SessionSummary)
    return result  # type: ignore[return-value]
