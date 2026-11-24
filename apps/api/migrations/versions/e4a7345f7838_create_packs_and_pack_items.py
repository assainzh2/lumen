"""create packs and pack_items

Revision ID: e4a7345f7838
Revises: 8c374ddb7617
Create Date: 2026-11-24 15:38:54.503534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a7345f7838'
down_revision: Union[str, Sequence[str], None] = '8c374ddb7617'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # A pack is a published, versioned snapshot of approved items.
    # version is the number the phone compares ("v3" is only how it's displayed).
    op.execute("""
        CREATE TABLE packs (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            version INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT packs_version_key UNIQUE (version),
            CONSTRAINT packs_version_positive_check CHECK (version >= 1)
        );
    """)
    # Join table: one row = "this item is in this pack".
    # RESTRICT on both sides: these rows are the record of what shipped to phones.
    op.execute("""
        CREATE TABLE pack_items (
            pack_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            CONSTRAINT pack_items_pkey PRIMARY KEY (pack_id, item_id),
            CONSTRAINT pack_items_pack_id_fkey
                FOREIGN KEY (pack_id) REFERENCES packs (id) ON DELETE RESTRICT,
            CONSTRAINT pack_items_item_id_fkey
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT
        );
    """)
    # The primary key index is sorted by pack_id first, so it can't serve
    # "which packs contain item X" or the RESTRICT check when an item is deleted.
    op.execute("""
        CREATE INDEX pack_items_item_id_idx ON pack_items (item_id);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP TABLE pack_items;
    """)
    op.execute("""
        DROP TABLE packs;
    """)
