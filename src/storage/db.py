from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Iterator

from src.models.orm import SCHEMA_SQL


def _sqlite_path_from_url(database_url: str) -> str:
    if database_url == ":memory:" or database_url == "sqlite:///:memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    return database_url


class Database:
    """SQLite database manager with automatic schema initialization."""

    def __init__(self, database_url: str = "sqlite:///pr_job_matcher.db") -> None:
        self.database_url = database_url
        self.sqlite_path = _sqlite_path_from_url(database_url)
        if self.sqlite_path != ":memory:":
            Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._shared_memory_conn: sqlite3.Connection | None = None
        if self.sqlite_path == ":memory:":
            self._shared_memory_conn = sqlite3.connect(":memory:")
            self._shared_memory_conn.row_factory = sqlite3.Row
            self._shared_memory_conn.execute("PRAGMA foreign_keys = ON;")
        self.init_schema()

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self._shared_memory_conn is not None:
            try:
                yield self._shared_memory_conn
                self._shared_memory_conn.commit()
            except Exception:
                self._shared_memory_conn.rollback()
                raise
            return

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        if self._shared_memory_conn is not None:
            self._shared_memory_conn.close()
            self._shared_memory_conn = None
