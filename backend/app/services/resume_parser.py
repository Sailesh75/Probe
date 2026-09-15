"""Extracts plain text from an uploaded resume file (PDF or DOCX).

The result rides into the same resume textarea as pasted text on the frontend — reviewed
and editable before starting a session, not submitted silently. Parsing (especially of PDFs
with multi-column layouts or odd encodings) can produce mangled text, so a review step matters
more here than for voice transcription.
"""

import io

import docx
import pdfplumber

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — resumes are text-dense but never this large


class UnsupportedFileType(ValueError):
    pass


class FileTooLarge(ValueError):
    pass


def extract_text(file_bytes: bytes, filename: str) -> str:
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileTooLarge(f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB limit")

    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    raise UnsupportedFileType(f"Unsupported file type: {filename} (use .pdf or .docx)")


def _extract_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError("Couldn't extract any text from this PDF (it may be scanned/image-only)")
    return text


def _extract_docx(file_bytes: bytes) -> str:
    document = docx.Document(io.BytesIO(file_bytes))
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    if not text:
        raise ValueError("Couldn't extract any text from this DOCX")
    return text
