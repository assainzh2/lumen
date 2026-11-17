import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
import psycopg
from sqlalchemy.exc import IntegrityError

# apps/api, where alembic.ini lives. Alembic must run from there.
API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def test_db_url() -> str:
    """URL of the throwaway database. Refuses to touch anything not named *_test."""
    url = os.environ.get("TEST_DATABASE_URL")
    database = sa.engine.make_url(url).database if url else None
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set (see .env.example)")
    if database is None or not database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point at a database whose name ends in _test")
    return url


def alembic(url: str, *args: str) -> None:
    """Run `alembic <args>` against the given database. Raises if Alembic fails."""
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": url},  # env.py reads this variable
        check=True,
    )


def table_exists(url: str, name: str) -> bool:
    """True if a table with this name exists. to_regclass returns NULL when it doesn't."""
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            result = conn.execute(sa.text("SELECT to_regclass(:name)"), {"name": name})
            return result.scalar() is not None
    finally:
        engine.dispose()


def test_sources_and_kinds_upgrade_and_downgrade(test_db_url: str) -> None:
    alembic(test_db_url, "downgrade", "base")  # start from an empty database
    alembic(test_db_url, "upgrade", "head")
    assert table_exists(test_db_url, "sources")
    assert table_exists(test_db_url, "kinds")
    alembic(test_db_url, "downgrade", "base")
    assert not table_exists(test_db_url, "sources")
    assert not table_exists(test_db_url, "kinds")

def test_items_foreign_keys(test_db_url: str) -> None:
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        # Parent rows: an item needs a real source and a real kind to point at.
        with engine.begin() as conn:
            source_id = conn.execute(sa.text(
                "INSERT INTO sources (url, text, licence) "
                "VALUES ('https://example.com/a', 'Slow breathing lowers stress.', 'CC BY-SA') "
                "RETURNING id"
            )).scalar_one()
            kind_id = conn.execute(sa.text(
                "INSERT INTO kinds (name) VALUES ('fact') RETURNING id"
            )).scalar_one()
            chunk_id = conn.execute(sa.text(
                "INSERT INTO chunks (source_id, position, text) "
                "VALUES (:source_id, 0, 'some text') RETURNING id"
            ), {"source_id": source_id}).scalar_one()

        # (OK) insert a valid item using source_id and kind_id.
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
                    "VALUES (:kind_id, :source_id, 'x', 'y', :chunk_id)"
                ),
                {"kind_id": kind_id, "source_id": source_id, "chunk_id": chunk_id},
            )

        # (A) An item pointing at a source that does not exist is refused.
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
                        "VALUES (:kind_id, 999999, 'x', 'y', :chunk_id)"
                    ),
                    {"kind_id": kind_id, "chunk_id": chunk_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)

        # (A2) same, but with a kind_id that does not exist.
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
                        "VALUES (999999, :source_id, 'x', 'y', :chunk_id)"
                    ),
                    {"source_id": source_id, "chunk_id": chunk_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
        # (C) deleting the source that the valid item uses is refused.
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "DELETE FROM sources WHERE id = :source_id"
                    ),
                    {"source_id": source_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    finally:
        engine.dispose()
    # downgrade back to base so the next test starts clean.
    alembic(test_db_url, "downgrade", "base")


def test_chunks_constraints(test_db_url: str) -> None:
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        # valid source
        with engine.begin() as conn:
            source_id = conn.execute(sa.text(
                "INSERT INTO sources (url, text, licence) "
                "VALUES ('https://example.com/a', 'Slow breathing lowers stress.', 'CC BY-SA') "
                "RETURNING id"
            )).scalar_one()
        # insert a valid chunk using source_id
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO chunks (source_id, position, text) "
                    "VALUES (:source_id, 0, :some_text)"
                ),
                {"source_id": source_id, "some_text": "some text"},
            )
        # (A) a chunk with a source_id that doesn't exist is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO chunks (source_id, position, text) "
                        "VALUES (999999, 0, 'some text')"
                    ),
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
        # (B) a second chunk with the same source_id and position is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO chunks (source_id, position, text) "
                        "VALUES (:source_id, 0, :some_text)"
                    ),
                    {"source_id": source_id, "some_text": "some text"},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)
        # OK insert a second chunk with the same source_id but a different position
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO chunks (source_id, position, text) "
                    "VALUES (:source_id, 1, :some_text)"
                ),
                {"source_id": source_id, "some_text": "some text"},
            )

        # (C) deleting the source that the valid chunk uses is refused.
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "DELETE FROM sources WHERE id = :source_id"
                    ),
                    {"source_id": source_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def insert_source(conn: sa.Connection, url: str) -> int:
    """Insert a minimal source row and return its id."""
    return conn.execute(
        sa.text(
            "INSERT INTO sources (url, text, licence) "
            "VALUES (:url, 'Some source text.', 'CC BY-SA') "
            "RETURNING id"
        ),
        {"url": url},
    ).scalar_one()


def test_chunks_position_is_unique_per_source_not_globally(test_db_url: str) -> None:
    """Chunk 0 of source A and chunk 0 of source B must both exist.

    Catches a wrong `UNIQUE (position)`, which the single-source test cannot.
    """
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            source_a = insert_source(conn, "https://example.com/a")
            source_b = insert_source(conn, "https://example.com/b")
        with engine.begin() as conn:
            for source_id in (source_a, source_b):
                conn.execute(
                    sa.text(
                        "INSERT INTO chunks (source_id, position, text) "
                        "VALUES (:source_id, 0, 'some text')"
                    ),
                    {"source_id": source_id},
                )
            count = conn.execute(
                sa.text("SELECT count(*) FROM chunks WHERE position = 0")
            ).scalar_one()
        assert count == 2
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_chunks_required_columns(test_db_url: str) -> None:
    """position and text are NOT NULL: a chunk without them is refused."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            source_id = insert_source(conn, "https://example.com/a")

        # (D) NULL text is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO chunks (source_id, position, text) "
                        "VALUES (:source_id, 0, NULL)"
                    ),
                    {"source_id": source_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)

        # (E) NULL position is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO chunks (source_id, position, text) "
                        "VALUES (:source_id, NULL, 'some text')"
                    ),
                    {"source_id": source_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_items_chunk_must_belong_to_same_source(test_db_url: str) -> None:
    """An item cannot point at a chunk that belongs to a different source."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        # OK an item with source A and the chunk of A is accepted
        with engine.begin() as conn:
            source_a = insert_source(conn, "https://example.com/a")
            source_b = insert_source(conn, "https://example.com/b")
            kind_id = conn.execute(sa.text(
                "INSERT INTO kinds (name) VALUES ('fact') RETURNING id"
            )).scalar_one()
            chunk_a_id = conn.execute(sa.text(
                "INSERT INTO chunks (source_id, position, text) "
                "VALUES (:source_id, 0, 'some text') RETURNING id"
            ), {"source_id": source_a}).scalar_one()
            chunk_b_id = conn.execute(sa.text(
                "INSERT INTO chunks (source_id, position, text) "
                "VALUES (:source_id, 0, 'some text') RETURNING id"
            ), {"source_id": source_b}).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
                    "VALUES (:kind_id, :source_id, 'x', 'y', :chunk_id)"
                ),
                {"kind_id": kind_id, "source_id": source_a, "chunk_id": chunk_a_id},
            )
        # (A) an item with source A but the chunk of B is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
                        "VALUES (:kind_id, :source_id, 'x', 'y', :chunk_id)"
                    ),
                    {"kind_id": kind_id, "source_id": source_a, "chunk_id": chunk_b_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)

        # (B) an item with chunk_id NULL is refused: NotNullViolation
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
                        "VALUES (:kind_id, :source_id, 'x', 'y', NULL)"
                    ),
                    {"kind_id": kind_id, "source_id": source_a},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)

        # (C) deleting a chunk that an item uses is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "DELETE FROM chunks WHERE id = :chunk_id"
                    ),
                    {"chunk_id": chunk_a_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")
