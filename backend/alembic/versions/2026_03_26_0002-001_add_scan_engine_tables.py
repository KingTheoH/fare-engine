"""002 add scan engine tables — scan_targets, dump_candidates, and new dump_pattern fields.

Revision ID: 002
Revises: 001
Create Date: 2026-03-26

Changes:
  - dump_patterns: make ita_routing_code nullable, add scan engine fields
  - New table: scan_targets (city pair × tier to drive the scanner)
  - New table: dump_candidates (short-haul segments to inject as dump legs)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==================== dump_patterns: new scan engine fields ====================

    # Make ita_routing_code nullable (was NOT NULL — we're moving away from single static codes)
    op.alter_column("dump_patterns", "ita_routing_code", nullable=True)

    # Baseline routing (no dump injection — just carrier + connection constraint)
    op.add_column(
        "dump_patterns",
        sa.Column(
            "baseline_routing",
            sa.Text(),
            nullable=True,
            comment="ITA Matrix routing code for baseline query (no dump injection)",
        ),
    )

    # Optimized routing (with dump segment injected)
    op.add_column(
        "dump_patterns",
        sa.Column(
            "optimized_routing",
            sa.Text(),
            nullable=True,
            comment="ITA Matrix routing code with dump segment injected",
        ),
    )

    # Multi-city segment structure (the full itinerary as JSONB)
    # Example: [{"from": "YVR", "to": "LHR", "carrier": "LH"},
    #           {"from": "LHR", "to": "TAS", "carrier": null}]
    op.add_column(
        "dump_patterns",
        sa.Column(
            "multi_city_segments",
            postgresql.JSONB(),
            nullable=True,
            comment="Ordered list of multi-city legs [{from, to, carrier, notes}]",
        ),
    )

    # The dump segment itself — the short-haul leg that triggers the misprice
    # Example: {"from": "LHR", "to": "OSL", "carrier": null, "notes": "loose short-haul"}
    op.add_column(
        "dump_patterns",
        sa.Column(
            "dump_segment",
            postgresql.JSONB(),
            nullable=True,
            comment="The injected short-haul segment that disrupts YQ calculation",
        ),
    )

    # Price delta model — what the scanner actually measures
    op.add_column(
        "dump_patterns",
        sa.Column(
            "baseline_price_usd",
            sa.Float(),
            nullable=True,
            comment="Price returned by ITA Matrix for the baseline routing (no dump)",
        ),
    )
    op.add_column(
        "dump_patterns",
        sa.Column(
            "optimized_price_usd",
            sa.Float(),
            nullable=True,
            comment="Price returned by ITA Matrix with the dump segment injected",
        ),
    )

    # When the scanner last successfully ran for this pattern
    op.add_column(
        "dump_patterns",
        sa.Column(
            "last_scan_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of the last scan run that produced a price delta",
        ),
    )

    # ==================== scan_targets ====================
    op.create_table(
        "scan_targets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "origin_iata",
            sa.String(3),
            nullable=False,
            comment="Origin airport (e.g. YVR, SEA, LHR)",
        ),
        sa.Column(
            "destination_iata",
            sa.String(3),
            nullable=False,
            comment="Destination airport (e.g. LHR, BKK, ICN)",
        ),
        sa.Column(
            "carrier_iata",
            sa.String(2),
            nullable=True,
            comment="Preferred carrier to test — NULL means try all high-YQ carriers",
        ),
        sa.Column(
            "tier",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="1=daily, 2=weekly, 3=monthly scan frequency",
        ),
        sa.Column(
            "last_scanned_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this target was last scanned",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Set to false to pause scanning this target",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "origin_iata", "destination_iata", "carrier_iata",
            name="uq_scan_target",
        ),
    )
    op.create_index("idx_scan_targets_tier_enabled", "scan_targets", ["tier", "enabled"])
    op.create_index("idx_scan_targets_route", "scan_targets", ["origin_iata", "destination_iata"])

    # ==================== dump_candidates ====================
    op.create_table(
        "dump_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "from_iata",
            sa.String(3),
            nullable=False,
            comment="Origin of the short-haul dump segment",
        ),
        sa.Column(
            "to_iata",
            sa.String(3),
            nullable=False,
            comment="Destination of the short-haul dump segment",
        ),
        sa.Column(
            "carrier_iata",
            sa.String(2),
            nullable=True,
            comment="Preferred carrier for this segment — NULL means leave loose (best for dumps)",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Why this segment works as a dump — pricing zone, alliance, etc.",
        ),
        # Success tracking — updated by the scanner
        sa.Column(
            "success_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Number of times this segment produced a price delta",
        ),
        sa.Column(
            "test_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Total number of times this segment was tested",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Set to false to exclude from scanner",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("from_iata", "to_iata", "carrier_iata", name="uq_dump_candidate"),
    )
    op.create_index("idx_dump_candidates_enabled", "dump_candidates", ["enabled"])


def downgrade() -> None:
    op.drop_table("dump_candidates")
    op.drop_table("scan_targets")

    op.drop_column("dump_patterns", "last_scan_at")
    op.drop_column("dump_patterns", "optimized_price_usd")
    op.drop_column("dump_patterns", "baseline_price_usd")
    op.drop_column("dump_patterns", "dump_segment")
    op.drop_column("dump_patterns", "multi_city_segments")
    op.drop_column("dump_patterns", "optimized_routing")
    op.drop_column("dump_patterns", "baseline_routing")

    # Restore NOT NULL on ita_routing_code — note: this will fail if any rows have NULL
    op.alter_column("dump_patterns", "ita_routing_code", nullable=False)
