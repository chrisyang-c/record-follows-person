from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = API_DIR.parent.parent
log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- model provider ----------------------------------------------------------------
    # openai    → ChatOpenAI(model=MODEL_PINNED, temperature=0)   (needs OPENAI_API_KEY)
    # anthropic → ChatAnthropic(model=MODEL_PINNED, temperature=0) (needs ANTHROPIC_API_KEY)
    # mock      → deterministic lexicon/templates, no network (tests, CI)
    # A provider whose key is missing degrades to mock with a warning so the demo still runs.
    MODEL_PROVIDER: Literal["mock", "openai", "anthropic"] = "openai"
    MODEL_PINNED: str = "gpt-4.1-2025-04-14"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

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
    def provider_key(self) -> str:
        return {"openai": self.OPENAI_API_KEY, "anthropic": self.ANTHROPIC_API_KEY}.get(
            self.MODEL_PROVIDER, ""
        )

    @property
    def llm_enabled(self) -> bool:
        """True when a real chat model will be used (provider set AND its key present)."""
        return self.MODEL_PROVIDER != "mock" and bool(self.provider_key)

    @property
    def effective_provider(self) -> str:
        return self.MODEL_PROVIDER if self.llm_enabled else "mock"

    def get_model(self) -> Any:
        """The one chat model factory. deep agents and every graph node go through here.

        Returns ChatOpenAI / ChatAnthropic pinned to MODEL_PINNED with temperature=0, or a
        deterministic fake chat model when MODEL_PROVIDER=mock or the provider key is absent.
        """
        if self.MODEL_PROVIDER == "openai" and self.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=self.MODEL_PINNED, temperature=0, api_key=self.OPENAI_API_KEY, max_retries=6
            )
        if self.MODEL_PROVIDER == "anthropic" and self.ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=self.MODEL_PINNED, temperature=0, api_key=self.ANTHROPIC_API_KEY
            )
        if self.MODEL_PROVIDER != "mock":
            log.warning(
                "MODEL_PROVIDER=%s but no API key; using the mock model", self.MODEL_PROVIDER
            )
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage

        return GenericFakeChatModel(messages=iter([AIMessage(content="（mock 模型：無網路）")]))


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_model() -> Any:
    """Module-level convenience: get_settings().get_model()."""
    return get_settings().get_model()
