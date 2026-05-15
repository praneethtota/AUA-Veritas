"""
core/state.py — AUA-Veritas local state store.
Simplified from AUA's state.py: single-user SQLite, no blue-green tables.
COPIED from aua/state.py then modified — see docs/COPY-LOG.md
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)


class VeritasState:
    """Thread-safe SQLite state store for AUA-Veritas."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
        if schema_path.exists():
            ddl = schema_path.read_text()
            with self._conn() as conn:
                conn.executescript(ddl)
        # Ensure local user row exists
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(user_id, created_at) VALUES ('local', ?)",
                (time.time(),)
            )

    def append(self, table: str, record: dict) -> str:
        """Insert a record. Only auto-generates an ID if no *_id key is present."""
        has_any_id = "id" in record or any(k.endswith("_id") for k in record)
        if not has_any_id:
            id_key = f"{table[:-1]}_id" if table.endswith("s") else "id"
            record = {id_key: str(uuid.uuid4()), **record}
        record.setdefault("created_at", time.time())
        cols = ", ".join(record.keys())
        placeholders = ", ".join("?" for _ in record)
        with self._conn() as conn:
            conn.execute(f"INSERT OR IGNORE INTO {table}({cols}) VALUES ({placeholders})",
                        list(record.values()))
        return list(record.values())[0]

    def query(self, table: str, filters: dict | None = None, limit: int = 100) -> list[dict]:
        where_parts = []
        params = []
        if filters:
            for k, v in filters.items():
                where_parts.append(f"{k} = ?")
                params.append(v)
        where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} {where} LIMIT {limit}", params
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, table: str, key: str, key_col: str | None = None) -> dict | None:
        if key_col is None:
            # guess key column
            key_col = f"{table[:-1]}_id" if table.endswith("s") else "id"
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE {key_col} = ?", (key,)
            ).fetchone()
        return dict(row) if row else None
