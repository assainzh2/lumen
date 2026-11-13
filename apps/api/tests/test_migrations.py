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

        # (OK) insert a valid item using source_id and kind_id.
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO items (kind_id, source_id, card_text, quote) "
                    "VALUES (:kind_id, :source_id, 'x', 'y')"
                ),
                {"kind_id": kind_id, "source_id": source_id},
            )

        # (A) An item pointing at a source that does not exist is refused.
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO items (kind_id, source_id, card_text, quote) "
                        "VALUES (:kind_id, 999999, 'x', 'y')"
                    ),
                    {"kind_id": kind_id},
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)

        # (A2) same, but with a kind_id that does not exist.
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO items (kind_id, source_id, card_text, quote) "
                        "VALUES (999999, :source_id, 'x', 'y')"
                    ),
                    {"source_id": source_id},
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
