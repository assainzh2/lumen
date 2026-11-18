"""Constraints on the items table."""

import psycopg
import pytest
import sqlalchemy as sa
from helpers import insert_source
from sqlalchemy.exc import IntegrityError


def test_items_foreign_keys(engine: sa.Engine) -> None:
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


def test_items_chunk_must_belong_to_same_source(engine: sa.Engine) -> None:
    """An item cannot point at a chunk that belongs to a different source."""
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
