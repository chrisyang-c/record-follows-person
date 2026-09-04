"""Checkpointer: PostgresSaver when DATABASE_URL is reachable, InMemorySaver otherwise.

`saver.setup()` is ONLY executed by graphs/migrate.py (CLAUDE.md §4)."""

from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from core.settings import get_settings

log = logging.getLogger(__name__)


def _postgres_saver(url: str) -> BaseCheckpointSaver:
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row

    conn = psycopg.connect(url, autocommit=True, row_factory=dict_row, prepare_threshold=0)
    return PostgresSaver(conn)


@lru_cache
def get_checkpointer() -> BaseCheckpointSaver:
    url = get_settings().DATABASE_URL
    if url:
        try:
            saver = _postgres_saver(url)
            log.info("checkpointer: PostgresSaver")
            return saver
        except Exception as e:  # noqa: BLE001
            log.warning("PostgresSaver unavailable (%s); falling back to InMemorySaver", e)
    log.info("checkpointer: InMemorySaver")
    return InMemorySaver()


def is_postgres() -> bool:
    return type(get_checkpointer()).__name__ == "PostgresSaver"
