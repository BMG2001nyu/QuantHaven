from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_settings


def initialize_database(database_path: str | Path | None = None) -> Path:
    settings = get_settings()
    target = Path(database_path) if database_path else settings.database_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                qty TEXT NOT NULL,
                price TEXT NOT NULL,
                client_order_id TEXT NOT NULL UNIQUE,
                payload_hash TEXT NOT NULL,
                broker_ref TEXT NOT NULL,
                received_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    return target


@contextmanager
def get_connection(database_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    target = initialize_database(database_path)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
