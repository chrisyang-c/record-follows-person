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
    # openai    → ChatOpenAI(model=MODEL_PINNED, temperature=0, reasoning_effort=none for gpt-5.x)
    # anthropic → ChatAnthropic(model=MODEL_PINNED, temperature=0) (needs ANTHROPIC_API_KEY)
    # mock      → deterministic lexicon/templates, no network (tests, CI)
    # A provider whose key is missing degrades to mock with a warning so the demo still runs.
    MODEL_PROVIDER: Literal["mock", "openai", "anthropic"] = "openai"
    MODEL_PINNED: str = "gpt-5.6-luna"
    # reasoning_effort for the two intake calls (llm.extract, llm.next_question). "none" keeps
    # /chat/completions; anything else ("low"/"medium"/"high") switches those calls to the
    # Responses API (function tools + reasoning are rejected on chat completions, probed
    # 2026-09-05). Deep agents / other nodes always use "none".
    INTAKE_REASONING_EFFORT: str = "low"
    # USD per 1M tokens, used only for the cost estimate in trace / ACCEPTANCE (gpt-5.6-luna list
    # price after the 2026-07-30 cut: input 0.20, cached input 0.02, cache write 0.25, output 1.20)
    PRICE_INPUT_PER_M: float = 0.20
    PRICE_CACHED_INPUT_PER_M: float = 0.02
    PRICE_CACHE_WRITE_PER_M: float = 0.25
    PRICE_OUTPUT_PER_M: float = 1.20
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

    @property
    def prices(self) -> dict[str, float]:
        return {
            "input": self.PRICE_INPUT_PER_M,
            "cached_input": self.PRICE_CACHED_INPUT_PER_M,
            "cache_write": self.PRICE_CACHE_WRITE_PER_M,
            "output": self.PRICE_OUTPUT_PER_M,
        }

    def get_model(self, reasoning_effort: str = "none") -> Any:
        """The one chat model factory. deep agents and every graph node go through here.

        Returns ChatOpenAI / ChatAnthropic pinned to MODEL_PINNED with temperature=0, or a
        deterministic fake chat model when MODEL_PROVIDER=mock or the provider key is absent.
        ``reasoning_effort`` only applies to gpt-5.x: "none" → /chat/completions; any other
        value → Responses API (``use_responses_api=True``), because chat completions rejects
        function tools together with reasoning on gpt-5.6-luna (probed 2026-09-05).
        """
        if self.MODEL_PROVIDER == "openai" and self.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI

            from core.usage import UsageTrace

            extra: dict[str, Any] = {}
            if self.MODEL_PINNED.startswith("gpt-5"):
                # gpt-5.x on /chat/completions: function tools need reasoning_effort="none", and
                # temperature=0 is only accepted together with it (probed 2026-09-05).
                extra["reasoning_effort"] = reasoning_effort or "none"
                if extra["reasoning_effort"] != "none":
                    extra["use_responses_api"] = True
            return ChatOpenAI(
                model=self.MODEL_PINNED,
                temperature=0,
                api_key=self.OPENAI_API_KEY,
                max_retries=6,
                callbacks=[UsageTrace(self.MODEL_PINNED, self.prices)],
                **extra,
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
