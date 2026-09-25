from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


class Database:
    def __init__(self, url: str | None = None) -> None:
        resolved_url = url or os.environ.get("DATABASE_URL")
        if not resolved_url:
            raise ValueError("Set DATABASE_URL to a Postgres connection string")
        self.url: str = resolved_url

    @contextmanager
    def connect(self) -> Iterator[Connection[dict[str, Any]]]:
        # psycopg commits on clean exit and rolls back on exception.
        with psycopg.connect(self.url, row_factory=dict_row, connect_timeout=5) as connection:
            yield connection

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(90210431)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, checksum text NOT NULL)"
            )
            for migration in sorted(files("brief").joinpath("migrations").iterdir(), key=lambda p: p.name):
                if not migration.name.endswith(".sql"):
                    continue
                sql = migration.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                previous = connection.execute(
                    "SELECT checksum FROM schema_migrations WHERE name = %s", (migration.name,)
                ).fetchone()
                if previous:
                    if previous["checksum"] != checksum:
                        raise ValueError(f"Applied migration changed: {migration.name}")
                    continue
                connection.execute(sql)
                connection.execute("INSERT INTO schema_migrations VALUES (%s, %s)", (migration.name, checksum))


def require_row(row: dict[str, Any] | None) -> dict[str, Any]:
    """Require a row from a query whose caller relies on its existence."""
    if row is None:
        raise LookupError("Expected database row was not found")
    return row
