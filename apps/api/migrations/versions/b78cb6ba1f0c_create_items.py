"""create items

Revision ID: b78cb6ba1f0c
Revises: 2afdef349562
Create Date: 2026-11-13 13:24:54.109241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b78cb6ba1f0c'
down_revision: Union[str, Sequence[str], None] = '2afdef349562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""CREATE TABLE items (
        id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        kind_id INTEGER NOT NULL REFERENCES kinds(id) ON DELETE RESTRICT,
        source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
        card_text TEXT NOT NULL,
        quote TEXT NOT NULL
    )""")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE items")
