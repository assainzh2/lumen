"""Alembic round trip: upgrade creates the tables, downgrade removes them.

Table rules (constraints) are tested in the per-table files, e.g. test_reviews.py.
"""
from helpers import alembic, table_exists


def test_sources_and_kinds_upgrade_and_downgrade(test_db_url: str) -> None:
    alembic(test_db_url, "downgrade", "base")  # start from an empty database
    alembic(test_db_url, "upgrade", "head")
    assert table_exists(test_db_url, "sources")
    assert table_exists(test_db_url, "kinds")
    alembic(test_db_url, "downgrade", "base")
    assert not table_exists(test_db_url, "sources")
    assert not table_exists(test_db_url, "kinds")
