import time
from functools import lru_cache

import requests
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import get_settings

# gemini-2.0-flash (the plan's original pick) and its stable successor gemini-2.5-flash have
# both since been retired for new users. gemini-3.6-flash is what Google's own API currently
# points new callers to. Revisit if a newer stable flash model ships.
MODEL = "gemini-3.6-flash"

# 429 (rate limit) and 5xx (transient server-side issues, e.g. "high demand" 503s we've hit
# in practice) are worth retrying; 4xx like 400/401/404 mean the request itself is broken.
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 2.0

# google-genai's HttpOptions.timeout has NO default (None) — without setting one, a stalled
# connection to Gemini hangs the request indefinitely instead of failing. Hit this for real in
# testing (a request sat for 5+ minutes with no response). 30s per attempt, retried below.
_REQUEST_TIMEOUT_MS = 30_000
_RETRYABLE_NETWORK_ERRORS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError)


@lru_cache
def get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def generate_structured(prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Call Gemini and force the response to match `schema`, returning a parsed instance.

    Retries transient errors (rate limits, "high demand" 5xxs, stalled connections) with
    backoff before giving up — these are common with the free tier and shouldn't surface as
    a hard failure (or an indefinite hang) on the first hit.
    """
    client = get_client()
    last_error: Exception | None = None

    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
                ),
            )
            if response.parsed is None:
                raise ValueError(f"Gemini returned unparseable output: {response.text!r}")
            return response.parsed
        except errors.APIError as exc:
            if exc.code not in _RETRYABLE_CODES or attempt == _MAX_ATTEMPTS - 1:
                raise
            last_error = exc
        except _RETRYABLE_NETWORK_ERRORS as exc:
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            last_error = exc
        # Only reached after a caught, retryable error — a successful call already returned.
        time.sleep(_BACKOFF_SECONDS * (2**attempt))

    # Unreachable — the loop above always either returns or raises — but keeps type checkers happy.
    assert last_error is not None
    raise last_error
