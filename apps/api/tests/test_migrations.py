import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

# apps/api, where alembic.ini lives. Alembic must run from there.
API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def test_db_url() -> str:
    """URL of the throwaway database. Refuses to touch anything not named *_test."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url is None:
        pytest.fail("TEST_DATABASE_URL is not set (see .env.example)")
    if not sa.engine.make_url(url).database.endswith("_test"):
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
