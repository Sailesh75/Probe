import logging
import time
from collections.abc import Callable
from functools import lru_cache
from typing import TypeVar

import requests
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

# gemini-2.0-flash (an earlier pick) and its stable successor gemini-2.5-flash have both since
# been retired for new users. gemini-3.6-flash is what Google's own API currently points new
# callers to. Revisit if a newer stable flash model ships. Also handles audio input natively
# (verified against real speech) — voice transcription reuses this same model instead of
# adding a separate Whisper API key/billing setup.
MODEL = "gemini-3.6-flash"

# Tried in order if MODEL is persistently overloaded/rate-limited (not just retried against
# the same overloaded model). Both verified live and structured-output-capable. Lighter models
# than MODEL, but functional — availability beats top capability for a fallback. A same-provider
# fallback, not a cross-provider one (e.g. DeepSeek): no new account/key, and it reuses Gemini's
# native response_schema enforcement instead of needing a separate JSON-mode + manual-parsing
# path. Bonus: each model likely has its own separate free-tier daily quota bucket, so this also
# helps against the 429 daily-cap case, not just 5xx "high demand" outages.
MODEL_FALLBACKS = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite"]

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

T = TypeVar("T")


class GeminiUnavailableError(RuntimeError):
    """Raised when every model in the fallback chain failed with a retryable error — a quota
    exhaustion (429) or a sustained outage (5xx/network) on Google's side, not a bug in our
    code. Callers (routers) catch this specifically to tell the user plainly what's wrong
    instead of surfacing a raw google.genai error blob."""

    def __init__(self, cause: Exception):
        self.cause = cause
        self.is_quota = isinstance(cause, errors.APIError) and cause.code == 429
        super().__init__(str(cause))

    def user_message(self) -> str:
        """A clean, user-facing explanation — never the raw google.genai error blob."""
        if self.is_quota:
            return (
                "The AI service has hit its usage quota for now. This resets daily — "
                "please try again later."
            )
        return (
            "The AI service is temporarily unavailable (high demand on Google's side). "
            "This is usually short-lived — please try again in a minute."
        )


@lru_cache
def get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _with_retry(call: Callable[[str], T]) -> T:
    """Falls back through MODEL_FALLBACKS if a model errors, retrying with backoff only on
    the last model in the chain. A non-retryable error (a genuinely broken request) still
    fails immediately, on any model. Shared by every Gemini call shape (structured JSON,
    audio transcription, ...).

    Earlier models get exactly one attempt before moving on — no backoff. In practice a
    "high demand" 503 on the primary model tends to be a sustained outage, not a one-off
    blip that clears within a couple of retries (confirmed in testing: every retry on the
    primary failed, every fallback succeeded on its first try) — so retrying the same
    struggling model 3 times with backoff before ever trying a different one just adds
    ~10s of dead time to every single request for no benefit. Full retry-with-backoff is
    reserved for the last model, since there's nowhere left to fall back to from there.
    """
    models = [MODEL, *MODEL_FALLBACKS]
    last_error: Exception | None = None

    for model_index, model in enumerate(models):
        is_last_model = model_index == len(models) - 1
        attempts = _MAX_ATTEMPTS if is_last_model else 1

        for attempt in range(attempts):
            try:
                return call(model)
            except errors.APIError as exc:
                if exc.code not in _RETRYABLE_CODES:
                    raise
                last_error = exc
            except _RETRYABLE_NETWORK_ERRORS as exc:
                last_error = exc

            is_last_attempt = attempt == attempts - 1
            if is_last_attempt and is_last_model:
                raise GeminiUnavailableError(last_error) from last_error
            if not is_last_attempt:
                time.sleep(_BACKOFF_SECONDS * (2**attempt))
            # else: this model's attempts are exhausted but another model remains — move on
            # immediately, no backoff needed (a different model isn't subject to the same
            # rate limit/overload).

        if last_error is not None:
            logger.warning("Gemini model %s exhausted, falling back to next model", model)

    # Unreachable — the loop above always either returns or raises — but keeps type checkers happy.
    assert last_error is not None
    raise GeminiUnavailableError(last_error) from last_error


def generate_structured(prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Call Gemini and force the response to match `schema`, returning a parsed instance."""
    client = get_client()

    def call(model: str) -> BaseModel:
        response = client.models.generate_content(
            model=model,
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

    return _with_retry(call)


def transcribe_audio(audio_bytes: bytes, mime_type: str, prompt: str) -> str:
    """Send audio straight to Gemini and get back plain text — no separate speech API."""
    client = get_client()

    def call(model: str) -> str:
        response = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type), prompt],
            config=types.GenerateContentConfig(http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS)),
        )
        if not response.text:
            raise ValueError("Gemini returned an empty transcription")
        return response.text

    return _with_retry(call)
