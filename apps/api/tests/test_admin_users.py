"""Constraints on the admin_users table."""

import psycopg
import pytest
import sqlalchemy as sa
from helpers import insert_admin_user
from sqlalchemy.exc import IntegrityError


def test_admin_users_insert_sets_created_at(engine: sa.Engine) -> None:
    """A valid admin user is accepted and created_at is filled in by default."""
    with engine.begin() as conn:
        admin_id = insert_admin_user(conn, "a@example.com")
        created_at = conn.execute(
            sa.text("SELECT created_at FROM admin_users WHERE id = :id"),
            {"id": admin_id},
        ).scalar_one()
    assert created_at is not None


def test_admin_users_email_is_unique(engine: sa.Engine) -> None:
    """The same email cannot be registered twice."""
    with engine.begin() as conn:
        insert_admin_user(conn, "a@example.com")

    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_admin_user(conn, "a@example.com", "other-hash")
    assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)


def test_admin_users_password_hash_is_not_unique(engine: sa.Engine) -> None:
    """Two different admins may share a password_hash value.

    Catches a wrong UNIQUE on password_hash instead of email.
    """
    with engine.begin() as conn:
        insert_admin_user(conn, "a@example.com", "same-hash")
        insert_admin_user(conn, "b@example.com", "same-hash")
        count = conn.execute(
            sa.text("SELECT count(*) FROM admin_users WHERE password_hash = 'same-hash'")
        ).scalar_one()
    assert count == 2


def test_admin_users_required_columns(engine: sa.Engine) -> None:
    """email and password_hash are NOT NULL."""
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


def test_admin_users_email_uniqueness_ignores_case(engine: sa.Engine) -> None:
    """a@example.com and A@example.com are the same admin.

    Catches a plain UNIQUE (email), which treats them as different.
    """
    with engine.begin() as conn:
        insert_admin_user(conn, "a@example.com", "x")
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_admin_user(conn, "A@example.com", "y")
    assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)


def test_created_at_is_required(engine: sa.Engine) -> None:
    """created_at is NOT NULL: a row without it is refused."""
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO admin_users (email, password_hash, created_at) "
                "VALUES ('a@example.com', 'x', NULL)"
            ))
    assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)
