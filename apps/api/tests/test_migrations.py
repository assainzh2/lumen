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


def test_admin_users_insert_sets_created_at(test_db_url: str) -> None:
    """A valid admin user is accepted and created_at is filled in by default."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            admin_id = insert_admin_user(conn, "a@example.com")
            created_at = conn.execute(
                sa.text("SELECT created_at FROM admin_users WHERE id = :id"),
                {"id": admin_id},
            ).scalar_one()
        assert created_at is not None
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_admin_users_email_is_unique(test_db_url: str) -> None:
    """The same email cannot be registered twice."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            insert_admin_user(conn, "a@example.com")

        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_admin_user(conn, "a@example.com", "other-hash")
        assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_admin_users_password_hash_is_not_unique(test_db_url: str) -> None:
    """Two different admins may share a password_hash value.

    Catches a wrong UNIQUE on password_hash instead of email.
    """
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            insert_admin_user(conn, "a@example.com", "same-hash")
            insert_admin_user(conn, "b@example.com", "same-hash")
            count = conn.execute(
                sa.text("SELECT count(*) FROM admin_users WHERE password_hash = 'same-hash'")
            ).scalar_one()
        assert count == 2
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_admin_users_required_columns(test_db_url: str) -> None:
    """email and password_hash are NOT NULL."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        # NULL email is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "INSERT INTO admin_users (email, password_hash) VALUES (NULL, 'x')"
                ))
        assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)

        # NULL password_hash is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "INSERT INTO admin_users (email, password_hash) VALUES ('a@example.com', NULL)"
                ))
        assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_admin_users_email_uniqueness_ignores_case(test_db_url: str) -> None:
    """a@example.com and A@example.com are the same admin.

    Catches a plain UNIQUE (email), which treats them as different.
    """
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            insert_admin_user(conn, "a@example.com", "x")
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_admin_user(conn, "A@example.com", "y")
        assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")



def test_created_at_is_required(test_db_url: str) -> None:
    """created_at is NOT NULL: a row without it is refused."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "INSERT INTO admin_users (email, password_hash, created_at) "
                    "VALUES ('a@example.com', 'x', NULL)"
                ))
        assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def insert_kind(conn: sa.Connection, name: str = "fact") -> int:
    """Insert a kind and return its id."""
    return conn.execute(
        sa.text("INSERT INTO kinds (name) VALUES (:name) RETURNING id"),
        {"name": name},
    ).scalar_one()


def test_reviews_accepts_valid_rows(test_db_url: str) -> None:
    """Approved without reason, rejected with reason, approved with a note: all accepted.

    Catches CHECK (reason IS NOT NULL) (row 1) and
    CHECK ((decision = 'approved') = (reason IS NULL)) (row 3).
    Each review gets its own item so a wrong UNIQUE (item_id) can't break this test.
    """
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_a = insert_item(conn, kind_id, "https://example.com/a")
            item_b = insert_item(conn, kind_id, "https://example.com/b")
            item_c = insert_item(conn, kind_id, "https://example.com/c")
            reviewer_id = insert_admin_user(conn, "a@example.com")
            review_id = insert_review(conn, item_a, reviewer_id, "approved", None)
            insert_review(conn, item_b, reviewer_id, "rejected", "too vague")
            insert_review(conn, item_c, reviewer_id, "approved", "good source")
            decided_at = conn.execute(
                sa.text("SELECT decided_at FROM reviews WHERE id = :id"),
                {"id": review_id},
            ).scalar_one()
        assert decided_at is not None
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_reviews_foreign_keys(test_db_url: str) -> None:
    """Reviews must point at a real item and a real admin; neither can be deleted under it."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_id = insert_item(conn, kind_id, "https://example.com/a")
            reviewer_id = insert_admin_user(conn, "a@example.com")
            insert_review(conn, item_id, reviewer_id, "approved", None)

        # (A) unknown item is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_review(conn, 999999, reviewer_id, "approved", None)
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)

        # (B) unknown reviewer is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_review(conn, item_id, 999999, "approved", None)
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)

        # (C) deleting a reviewed item is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text("DELETE FROM items WHERE id = :id"), {"id": item_id}
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)

        # (D) deleting a reviewer who has reviews is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                conn.execute(
                    sa.text("DELETE FROM admin_users WHERE id = :id"), {"id": reviewer_id}
                )
        assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_reviews_required_columns(test_db_url: str) -> None:
    """item_id, reviewer_id, decision and decided_at are NOT NULL."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_id = insert_item(conn, kind_id, "https://example.com/a")
            reviewer_id = insert_admin_user(conn, "a@example.com")

        cases = [
            "INSERT INTO reviews (item_id, reviewer_id, decision) "
            "VALUES (NULL, :reviewer_id, 'approved')",
            "INSERT INTO reviews (item_id, reviewer_id, decision) "
            "VALUES (:item_id, NULL, 'approved')",
            "INSERT INTO reviews (item_id, reviewer_id, decision) "
            "VALUES (:item_id, :reviewer_id, NULL)",
            "INSERT INTO reviews (item_id, reviewer_id, decision, decided_at) "
            "VALUES (:item_id, :reviewer_id, 'approved', NULL)",
        ]
        for sql in cases:
            with pytest.raises(IntegrityError) as excinfo:
                with engine.begin() as conn:
                    conn.execute(
                        sa.text(sql), {"item_id": item_id, "reviewer_id": reviewer_id}
                    )
            assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation), sql
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_reviews_decision_values(test_db_url: str) -> None:
    """decision is exactly 'approved' or 'rejected' (case-sensitive)."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_id = insert_item(conn, kind_id, "https://example.com/a")
            reviewer_id = insert_admin_user(conn, "a@example.com")

        # (A) an unknown decision is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_review(conn, item_id, reviewer_id, "pending", "r")
        assert isinstance(excinfo.value.orig, psycopg.errors.CheckViolation)
        assert excinfo.value.orig.diag.constraint_name == "reviews_decision_check"

        # (B) wrong case is refused
        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_review(conn, item_id, reviewer_id, "Approved", "r")
        assert isinstance(excinfo.value.orig, psycopg.errors.CheckViolation)
        assert excinfo.value.orig.diag.constraint_name == "reviews_decision_check"
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_reviews_rejection_requires_reason(test_db_url: str) -> None:
    """A rejection without a reason is refused."""
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_id = insert_item(conn, kind_id, "https://example.com/a")
            reviewer_id = insert_admin_user(conn, "a@example.com")

        with pytest.raises(IntegrityError) as excinfo:
            with engine.begin() as conn:
                insert_review(conn, item_id, reviewer_id, "rejected", None)
        assert isinstance(excinfo.value.orig, psycopg.errors.CheckViolation)
        assert excinfo.value.orig.diag.constraint_name == "reviews_reason_required_check"
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_reviews_allow_many_per_item(test_db_url: str) -> None:
    """An item can be reviewed many times; history is kept, latest wins.

    Catches a wrong UNIQUE (item_id) or UNIQUE (item_id, reviewer_id).
    """
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_a = insert_item(conn, kind_id, "https://example.com/a")
            item_b = insert_item(conn, kind_id, "https://example.com/b")
            reviewer_id = insert_admin_user(conn, "a@example.com")
            insert_review(conn, item_a, reviewer_id, "approved", None)
            insert_review(conn, item_b, reviewer_id, "rejected", "too vague")
            insert_review(conn, item_a, reviewer_id, "rejected", "duplicate")
            count = conn.execute(sa.text("SELECT count(*) FROM reviews")).scalar_one()
        assert count == 3
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")


def test_reviews_reason_not_blank(test_db_url: str) -> None:
    """A reason, when given, must contain a non-whitespace character, for any decision.

    '' is not NULL, so reviews_reason_required_check accepts it; only the
    not-blank check can refuse these rows. The 'approved' case catches a check
    that only guards rejections.
    """
    alembic(test_db_url, "downgrade", "base")
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            kind_id = insert_kind(conn)
            item_id = insert_item(conn, kind_id, "https://example.com/a")
            reviewer_id = insert_admin_user(conn, "a@example.com")

        cases = [
            ("rejected", ""),
            ("rejected", "   "),
            ("rejected", "\n"),
            ("approved", ""),
        ]
        for decision, reason in cases:
            with pytest.raises(IntegrityError) as excinfo:
                with engine.begin() as conn:
                    insert_review(conn, item_id, reviewer_id, decision, reason)
            assert isinstance(excinfo.value.orig, psycopg.errors.CheckViolation)
            assert (
                excinfo.value.orig.diag.constraint_name == "reviews_reason_not_blank_check"
            ), (decision, reason)
    finally:
        engine.dispose()
    alembic(test_db_url, "downgrade", "base")

