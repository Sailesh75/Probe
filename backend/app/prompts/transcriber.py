from app.llm.gemini_client import transcribe_audio

PROMPT = (
    "Transcribe this audio exactly as spoken. Return plain text only — no timestamps, "
    "speaker labels, or commentary. If the audio is silent or unintelligible, return an "
    "empty string rather than guessing."
)


def transcribe_answer(audio_bytes: bytes, mime_type: str) -> str:
    """Speech-to-text for voice answers. The result rides into the same answer textarea as
    typed text — reviewed and editable before submit, same pattern as resume text extraction,
    since transcription can be wrong and shouldn't silently commit to the interview."""
    return transcribe_audio(audio_bytes, mime_type, PROMPT).strip()
