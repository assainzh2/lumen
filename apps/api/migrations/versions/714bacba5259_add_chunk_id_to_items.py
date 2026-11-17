"""add chunk_id to items

Revision ID: 714bacba5259
Revises: 081e168cac09
Create Date: 2026-11-17 12:20:06.459638

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '714bacba5259'
down_revision: Union[str, Sequence[str], None] = '081e168cac09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # The foreign key below must point at a pair that is explicitly UNIQUE.
    op.execute(
        "ALTER TABLE chunks "
        "ADD CONSTRAINT chunks_id_source_id_key UNIQUE (id, source_id)"
    )
    op.execute("ALTER TABLE items ADD COLUMN chunk_id INTEGER NOT NULL")
    # Composite foreign key: the (chunk, source) pair must exist in chunks, so an
    # item can never cite a chunk that belongs to a different source.
    op.execute(
        "ALTER TABLE items "
        "ADD CONSTRAINT items_chunk_id_source_id_fkey "
        "FOREIGN KEY (chunk_id, source_id) REFERENCES chunks (id, source_id) "
        "ON DELETE RESTRICT"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Dropping the column also drops the foreign key that uses it; that must happen
    # before the unique constraint it depends on can be dropped.
    op.execute("ALTER TABLE items DROP COLUMN chunk_id")
    op.execute("ALTER TABLE chunks DROP CONSTRAINT chunks_id_source_id_key")
