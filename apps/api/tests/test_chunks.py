"""Constraints on the chunks table."""

import psycopg
import pytest
import sqlalchemy as sa
from helpers import insert_source
from sqlalchemy.exc import IntegrityError


def test_chunks_constraints(engine: sa.Engine) -> None:
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


def test_chunks_position_is_unique_per_source_not_globally(engine: sa.Engine) -> None:
    """Chunk 0 of source A and chunk 0 of source B must both exist.

    Catches a wrong `UNIQUE (position)`, which the single-source test cannot.
    """
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


def test_chunks_required_columns(engine: sa.Engine) -> None:
    """position and text are NOT NULL: a chunk without them is refused."""
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
