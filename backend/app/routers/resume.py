import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.services.resume_parser import FileTooLarge, UnsupportedFileType, extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])


class ParseResumeResponse(BaseModel):
    text: str


@router.post("/parse", response_model=ParseResumeResponse)
async def parse_resume(
    file: UploadFile, user_id=Depends(get_current_user_id)
) -> ParseResumeResponse:
    """Extracts plain text from an uploaded PDF/DOCX resume. The frontend drops the result
    into the same editable textarea as pasted text — reviewed before starting a session,
    never submitted silently, since parsing can mangle multi-column layouts or odd encodings.
    """
    file_bytes = await file.read()
    try:
        text = extract_text(file_bytes, file.filename or "")
    except (UnsupportedFileType, FileTooLarge) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("resume parsing failed for %s", file.filename)
        raise HTTPException(status_code=422, detail=f"Couldn't parse this file: {exc}") from exc

    return ParseResumeResponse(text=text)
