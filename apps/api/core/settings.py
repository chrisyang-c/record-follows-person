from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = API_DIR.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_MODE: Literal["mock", "anthropic"] = "mock"
    ANTHROPIC_API_KEY: str = ""
    MODEL_PINNED: str = "claude-sonnet-5"
    DATABASE_URL: str = ""
    LINE_CHANNEL_TOKEN: str = ""
    LINE_FAMILY_TO: str = ""
    RECORDS_ROOT: str = "../../records"
    NURSE_REVIEW_TIMEOUT_S: int = 600
    WORKER_SCAN_INTERVAL_S: int = 30

    @property
    def records_root(self) -> Path:
        p = Path(self.RECORDS_ROOT)
        return p if p.is_absolute() else (API_DIR / p).resolve()

    @property
    def llm_enabled(self) -> bool:
        return self.LLM_MODE == "anthropic" and bool(self.ANTHROPIC_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()
