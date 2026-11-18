"""Shared pytest fixtures. pytest loads this file automatically for every test in tests/."""
import os
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from helpers import alembic


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


@pytest.fixture
def engine(test_db_url: str) -> Iterator[sa.Engine]:
    """An engine on a freshly migrated, empty database.

    Everything before `yield` is setup, everything after it is teardown.
    pytest runs the teardown even when the test fails.
    """
    alembic(test_db_url, "downgrade", "base")  # start from an empty database
    alembic(test_db_url, "upgrade", "head")
    engine = sa.create_engine(test_db_url)
    yield engine
    engine.dispose()
    alembic(test_db_url, "downgrade", "base")
