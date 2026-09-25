from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from brief.db import Database
from brief.store import Store


@pytest.fixture
def database() -> Iterator[Database]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for real Postgres integration tests")
    schema = "test_" + uuid4().hex
    # Each test owns only its new schema, even when using a shared local database.
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    db = Database(make_conninfo(url, options=f"-c search_path={schema}"))
    try:
        db.migrate()
        yield db
    finally:
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def store(database: Database) -> Store:
    return Store(database)
