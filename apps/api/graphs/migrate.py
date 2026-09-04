"""The only place PostgresSaver.setup() runs, plus the thread registry table. `make migrate`."""

from __future__ import annotations

import sys

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from core.settings import get_settings
from graphs.registry import DDL


def main() -> int:
    url = get_settings().DATABASE_URL
    if not url:
        print("DATABASE_URL not set; nothing to migrate", file=sys.stderr)
        return 1
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as conn:
        PostgresSaver(conn).setup()
        conn.execute(DDL)
    print("migrated: langgraph checkpoint tables + threads registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
