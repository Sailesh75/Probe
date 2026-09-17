import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.llm.gemini_client import GeminiUnavailableError
from app.prompts.transcriber import transcribe_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_SIZE_BYTES = 15 * 1024 * 1024  # a few minutes of compressed speech audio


class TranscribeResponse(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile, user_id=Depends(get_current_user_id)) -> TranscribeResponse:
    """Speech-to-text for a recorded answer, via Gemini's native audio input — no separate
    Whisper API/key needed. The result rides into the same editable answer textarea as typed
    text, reviewed before submit rather than auto-submitted, since transcription can be wrong.
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Audio file too large (max 15MB)")

    mime_type = file.content_type or "audio/webm"
    try:
        text = transcribe_answer(file_bytes, mime_type)
    except GeminiUnavailableError as exc:
        logger.warning("voice transcription: Gemini unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=exc.user_message()) from exc
    except Exception as exc:
        logger.exception("audio transcription failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TranscribeResponse(text=text)
