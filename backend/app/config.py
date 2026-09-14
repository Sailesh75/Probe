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

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
