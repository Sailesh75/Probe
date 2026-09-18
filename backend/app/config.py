from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to backend/.env, not relative to cwd — otherwise this only works when a
# process happens to be launched from backend/ (uvicorn is; scripts run from the repo root,
# like eval/run_*.py, aren't).
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    gemini_api_key: str
    supabase_url: str
    supabase_key: str
    # Comma-separated allowed frontend origin(s) for CORS. Defaults to "*" for local dev
    # (any origin, e.g. http://localhost:5173) — set to the real deployed frontend URL in
    # production so the API isn't callable from arbitrary sites.
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        # Falls back to "*" rather than an empty (block-everything) list if CORS_ORIGINS ends
        # up set-but-blank — "briefly too permissive" is a smaller failure than "app broken",
        # and we use Bearer tokens (not cookies), so permissive CORS isn't a CSRF risk here.
        return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
