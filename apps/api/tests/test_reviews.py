"""Constraints on the reviews table."""

import psycopg
import pytest
import sqlalchemy as sa
from helpers import insert_admin_user, insert_item, insert_kind, insert_review
from sqlalchemy.exc import IntegrityError


def test_reviews_accepts_valid_rows(engine: sa.Engine) -> None:
    """Approved without reason, rejected with reason, approved with a note: all accepted.

    Catches CHECK (reason IS NOT NULL) (row 1) and
    CHECK ((decision = 'approved') = (reason IS NULL)) (row 3).
    Each review gets its own item so a wrong UNIQUE (item_id) can't break this test.
    """
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


def test_reviews_foreign_keys(engine: sa.Engine) -> None:
    """Reviews must point at a real item and a real admin; neither can be deleted under it."""
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


def test_reviews_required_columns(engine: sa.Engine) -> None:
    """item_id, reviewer_id, decision and decided_at are NOT NULL."""
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


def test_reviews_decision_values(engine: sa.Engine) -> None:
    """decision is exactly 'approved' or 'rejected' (case-sensitive)."""
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


def test_reviews_rejection_requires_reason(engine: sa.Engine) -> None:
    """A rejection without a reason is refused."""
    with engine.begin() as conn:
        kind_id = insert_kind(conn)
        item_id = insert_item(conn, kind_id, "https://example.com/a")
        reviewer_id = insert_admin_user(conn, "a@example.com")

    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_review(conn, item_id, reviewer_id, "rejected", None)
    assert isinstance(excinfo.value.orig, psycopg.errors.CheckViolation)
    assert excinfo.value.orig.diag.constraint_name == "reviews_reason_required_check"


def test_reviews_allow_many_per_item(engine: sa.Engine) -> None:
    """An item can be reviewed many times; history is kept, latest wins.

    Catches a wrong UNIQUE (item_id) or UNIQUE (item_id, reviewer_id).
    """
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


def test_reviews_reason_not_blank(engine: sa.Engine) -> None:
    """A reason, when given, must contain a non-whitespace character, for any decision.

    '' is not NULL, so reviews_reason_required_check accepts it; only the
    not-blank check can refuse these rows. The 'approved' case catches a check
    that only guards rejections.
    """
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
