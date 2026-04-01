"""003 add strike_segment — new STRIKE_SEGMENT dump type support.

Revision ID: 003
Revises: 002
Create Date: 2026-03-31

Changes:
  - dump_patterns: add strike_segment JSONB column (nullable)
    Stores the throwaway segment appended to a routing to zero YQ:
    {"origin": "SKD", "destination": "TAS", "carrier": "HY", "note": "..."}
  - DumpType enum now includes STRIKE_SEGMENT (string column, no DB enum change needed)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dump_patterns",
        sa.Column(
            "strike_segment",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Throwaway segment appended to end of routing to zero YQ {origin, destination, carrier, note}",
        ),
    )


def downgrade() -> None:
    op.drop_column("dump_patterns", "strike_segment")
