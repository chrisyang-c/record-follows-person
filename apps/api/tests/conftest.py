"""Graph tests run on a temp records root, InMemorySaver, mock LLM, zero nurse timeout."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ["MODEL_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = ""
os.environ["NURSE_REVIEW_TIMEOUT_S"] = "0"
os.environ["LINE_CHANNEL_TOKEN"] = ""

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "data" / "seed"))


@pytest.fixture(scope="session")
def records_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("records")
    os.environ["RECORDS_ROOT"] = str(root)
    from core.settings import get_settings

    get_settings.cache_clear()
    from record.store import get_store

    get_store.cache_clear()
    import seed as seed_mod

    seed_mod.seed(root, quiet=True)
    return root


@pytest.fixture(autouse=True)
def fresh_runner(records_root):
    from graphs import runner
    from graphs.checkpointer import get_checkpointer

    get_checkpointer.cache_clear()
    runner.reset_for_tests()
    yield
