from functools import lru_cache

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings

MODEL = "gemini-2.0-flash"


@lru_cache
def get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def generate_structured(prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Call Gemini and force the response to match `schema`, returning a parsed instance."""
    client = get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    if response.parsed is None:
        raise ValueError(f"Gemini returned unparseable output: {response.text!r}")
    return response.parsed
