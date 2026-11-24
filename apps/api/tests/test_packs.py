"""Constraints on the packs and pack_items tables."""

import psycopg
import pytest
import sqlalchemy as sa
from helpers import insert_item, insert_kind, insert_pack, insert_pack_item
from sqlalchemy.exc import IntegrityError


def test_packs_accept_valid_rows(engine: sa.Engine) -> None:
    """Packs v1 and v2; item A is in both packs, pack 2 holds items A and B.

    Catches a wrong UNIQUE (item_id) (A in two packs) or UNIQUE (pack_id)
    (two items in pack 2) on pack_items.
    """
    with engine.begin() as conn:
        kind_id = insert_kind(conn)
        item_a = insert_item(conn, kind_id, "https://example.com/a")
        item_b = insert_item(conn, kind_id, "https://example.com/b")
        pack1 = insert_pack(conn, version=1)
        pack2 = insert_pack(conn, version=2)
        insert_pack_item(conn, pack_id=pack1, item_id=item_a)
        insert_pack_item(conn, pack_id=pack2, item_id=item_a)
        insert_pack_item(conn, pack_id=pack2, item_id=item_b)
        created_at = conn.execute(
            sa.text("SELECT created_at FROM packs WHERE id = :id"),
            {"id": pack1},
        ).scalar_one()
        links = conn.execute(sa.text("SELECT count(*) FROM pack_items")).scalar_one()
    assert created_at is not None
    assert links == 3


def test_packs_version_rules(engine: sa.Engine) -> None:
    """version is unique, at least 1, and NOT NULL."""
    with engine.begin() as conn:
        insert_pack(conn, version=1)

    # (A) a duplicate version is refused
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_pack(conn, version=1)
    assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)
    assert excinfo.value.orig.diag.constraint_name == "packs_version_key"

    # (B) version 0 is refused
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_pack(conn, version=0)
    assert isinstance(excinfo.value.orig, psycopg.errors.CheckViolation)
    assert excinfo.value.orig.diag.constraint_name == "packs_version_positive_check"

    # (C) a NULL version is refused
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_pack(conn, version=None)
    assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)
    assert excinfo.value.orig.diag.column_name == "version"


def test_packs_created_at_not_null(engine: sa.Engine) -> None:
    """An explicit NULL created_at is refused.

    Leaving the column out would only test DEFAULT now(); this catches a missing NOT NULL.
    """
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO packs (version, created_at) VALUES (1, NULL)")
            )
    assert isinstance(excinfo.value.orig, psycopg.errors.NotNullViolation)
    assert excinfo.value.orig.diag.column_name == "created_at"


def test_pack_items_no_duplicates(engine: sa.Engine) -> None:
    """The same item can't be linked to the same pack twice (primary key on the pair)."""
    with engine.begin() as conn:
        kind_id = insert_kind(conn)
        item_a = insert_item(conn, kind_id, "https://example.com/a")
        pack1 = insert_pack(conn, version=1)
        insert_pack_item(conn, pack_id=pack1, item_id=item_a)

    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_pack_item(conn, pack_id=pack1, item_id=item_a)
    assert isinstance(excinfo.value.orig, psycopg.errors.UniqueViolation)
    assert excinfo.value.orig.diag.constraint_name == "pack_items_pkey"


def test_pack_items_foreign_keys(engine: sa.Engine) -> None:
    """Links must point at a real pack and item; neither can be deleted while linked.

    (A) unknown pack and (B) unknown item are refused.
    (C) deleting a linked item is refused, and the item is still there.
    (D) deleting a pack that has items is refused.
    (E) deleting the link first, then the item, succeeds.
    """
    with engine.begin() as conn:
        kind_id = insert_kind(conn)
        item_a = insert_item(conn, kind_id, "https://example.com/a")
        pack1 = insert_pack(conn, version=1)
        insert_pack_item(conn, pack_id=pack1, item_id=item_a)

    # (A) unknown pack is refused
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_pack_item(conn, pack_id=999999, item_id=item_a)
    assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    assert excinfo.value.orig.diag.constraint_name == "pack_items_pack_id_fkey"

    # (B) unknown item is refused
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            insert_pack_item(conn, pack_id=pack1, item_id=999999)
    assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    assert excinfo.value.orig.diag.constraint_name == "pack_items_item_id_fkey"

    # (C) deleting an item that is in a pack is refused, and the item survives
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM items WHERE id = :id"), {"id": item_a})
    assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    assert excinfo.value.orig.diag.constraint_name == "pack_items_item_id_fkey"
    with engine.begin() as conn:
        items_left = conn.execute(
            sa.text("SELECT count(*) FROM items WHERE id = :id"), {"id": item_a}
        ).scalar_one()
    assert items_left == 1

    # (D) deleting a pack that has items is refused
    with pytest.raises(IntegrityError) as excinfo:
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM packs WHERE id = :id"), {"id": pack1})
    assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)
    assert excinfo.value.orig.diag.constraint_name == "pack_items_pack_id_fkey"

    # (E) child first, then parent: the delete goes through
    with engine.begin() as conn:
        conn.execute(
            sa.text("DELETE FROM pack_items WHERE pack_id = :pack_id AND item_id = :item_id"),
            {"pack_id": pack1, "item_id": item_a},
        )
        conn.execute(sa.text("DELETE FROM items WHERE id = :id"), {"id": item_a})
        items_left = conn.execute(
            sa.text("SELECT count(*) FROM items WHERE id = :id"), {"id": item_a}
        ).scalar_one()
    assert items_left == 0
