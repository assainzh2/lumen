"""Plain helper functions shared by the test files (fixtures live in conftest.py)."""
import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

# apps/api, where alembic.ini lives. Alembic must run from there.
API_DIR = Path(__file__).resolve().parents[1]


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


def insert_kind(conn: sa.Connection, name: str = "fact") -> int:
    """Insert a kind and return its id."""
    return conn.execute(
        sa.text("INSERT INTO kinds (name) VALUES (:name) RETURNING id"),
        {"name": name},
    ).scalar_one()


def insert_admin_user(conn: sa.Connection, email: str, password_hash: str = "x") -> int:
    """Insert a minimal admin user and return its id."""
    return conn.execute(
        sa.text(
            "INSERT INTO admin_users (email, password_hash) "
            "VALUES (:email, :password_hash) "
            "RETURNING id"
        ),
        {"email": email, "password_hash": password_hash},
    ).scalar_one()


def insert_item(conn: sa.Connection, kind_id: int, source_url: str) -> int:
    """Insert a minimal item and return its id."""
    source_id = insert_source(conn, source_url)
    chunk_id = conn.execute(sa.text(
        "INSERT INTO chunks (source_id, position, text) "
        "VALUES (:source_id, 0, 'some text') RETURNING id"
    ), {"source_id": source_id}).scalar_one()
    return conn.execute(
        sa.text(
            "INSERT INTO items (kind_id, source_id, card_text, quote, chunk_id) "
            "VALUES (:kind_id, :source_id, 'x', 'y', :chunk_id) RETURNING id"
        ),
        {"kind_id": kind_id, "source_id": source_id, "chunk_id": chunk_id},
    ).scalar_one()


def insert_review(conn: sa.Connection, item_id: int, reviewer_id: int, decision: str, reason: str | None) -> int:
    """Insert a minimal review and return its id."""
    return conn.execute(
        sa.text(
            "INSERT INTO reviews (item_id, reviewer_id, decision, reason) "
            "VALUES (:item_id, :reviewer_id, :decision, :reason) RETURNING id"
        ),
        {"item_id": item_id, "reviewer_id": reviewer_id, "decision": decision, "reason": reason},
    ).scalar_one()
