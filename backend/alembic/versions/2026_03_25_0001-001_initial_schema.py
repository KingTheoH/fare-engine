"""001 initial schema — all tables and indexes for fare construction engine.

Revision ID: 001
Revises: (none)
Create Date: 2026-03-25

Tables created:
  - carriers
  - routes
  - dump_patterns
  - validation_runs
  - yq_schedules
  - community_posts

Indexes created per Phase 01 spec.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==================== carriers ====================
    op.create_table(
        "carriers",
        sa.Column("iata_code", sa.String(2), primary_key=True, comment="2-letter IATA airline code"),
        sa.Column("name", sa.String(100), nullable=False, comment="Full airline name"),
        sa.Column("alliance", sa.String(20), nullable=False, server_default="NONE", comment="STAR, ONEWORLD, SKYTEAM, or NONE"),
        sa.Column("charges_yq", sa.Boolean(), nullable=True, comment="Whether this carrier typically levies YQ"),
        sa.Column("typical_yq_usd", sa.Float(), nullable=True, comment="Approximate YQ per intercontinental roundtrip USD"),
        sa.Column("last_yq_updated", sa.DateTime(timezone=True), nullable=True, comment="When YQ data was last scraped"),
        sa.Column("yq_scrape_url", sa.String(500), nullable=True, comment="URL for scraping current YQ"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_carriers_charges_yq", "carriers", ["charges_yq"])

    # ==================== routes ====================
    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("origin_iata", sa.String(3), nullable=False, comment="3-letter IATA airport code"),
        sa.Column("destination_iata", sa.String(3), nullable=False, comment="3-letter IATA airport code"),
        sa.Column("is_intercontinental", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("origin_iata", "destination_iata", name="uq_route_pair"),
    )

    # ==================== dump_patterns ====================
    op.create_table(
        "dump_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # Classification
        sa.Column("dump_type", sa.String(30), nullable=False, comment="TP_DUMP, CARRIER_SWITCH, FARE_BASIS, ALLIANCE_RULE"),
        sa.Column("lifecycle_state", sa.String(20), nullable=False, server_default="discovered", comment="discovered, active, degrading, deprecated, archived"),
        # Route
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        # Carriers
        sa.Column("ticketing_carrier_iata", sa.String(2), nullable=False),
        sa.Column("operating_carriers", postgresql.ARRAY(sa.String(2)), nullable=False),
        sa.Column("routing_points", postgresql.ARRAY(sa.String(3)), nullable=False, server_default="{}"),
        # Fare construction
        sa.Column("fare_basis_hint", sa.String(50), nullable=True),
        sa.Column("ita_routing_code", sa.Text(), nullable=False, unique=True),
        sa.Column("manual_input_bundle", postgresql.JSONB(), nullable=True),
        # Scoring
        sa.Column("expected_yq_savings_usd", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("freshness_tier", sa.Integer(), nullable=False, server_default=sa.text("3")),
        # Source
        sa.Column("source", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_post_weight", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        # Backup
        sa.Column("backup_pattern_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dump_patterns.id", ondelete="SET NULL"), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_patterns_lifecycle_tier", "dump_patterns", ["lifecycle_state", "freshness_tier"])
    op.create_index("idx_patterns_route", "dump_patterns", ["origin_iata", "destination_iata"])
    op.create_index("idx_patterns_savings", "dump_patterns", [sa.text("expected_yq_savings_usd DESC")])

    # ==================== validation_runs ====================
    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pattern_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dump_patterns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        # Fare data
        sa.Column("yq_charged_usd", sa.Float(), nullable=True),
        sa.Column("yq_expected_usd", sa.Float(), nullable=True),
        sa.Column("base_fare_usd", sa.Float(), nullable=True),
        # Raw data
        sa.Column("raw_ita_response", postgresql.JSONB(), nullable=True),
        sa.Column("manual_input_snapshot", postgresql.JSONB(), nullable=True, comment="IMMUTABLE after creation"),
        # Error / Debug
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("proxy_used", sa.String(200), nullable=True),
    )
    op.create_index("idx_validations_pattern_time", "validation_runs", ["pattern_id", sa.text("ran_at DESC")])

    # ==================== yq_schedules ====================
    op.create_table(
        "yq_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("carrier_iata", sa.String(2), sa.ForeignKey("carriers.iata_code", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("yq_amount_usd", sa.Float(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
    )

    # ==================== community_posts ====================
    op.create_table(
        "community_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(30), nullable=False, server_default="FLYERTALK"),
        sa.Column("post_url", sa.String(500), nullable=False, unique=True),
        sa.Column("post_author", sa.String(100), nullable=True),
        sa.Column("author_post_count", sa.Integer(), nullable=True),
        sa.Column("author_account_age_days", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("extracted_patterns", postgresql.JSONB(), nullable=True),
        sa.Column("processing_state", sa.String(20), nullable=False, server_default="raw"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("community_posts")
    op.drop_table("yq_schedules")
    op.drop_table("validation_runs")
    op.drop_table("dump_patterns")
    op.drop_table("routes")
    op.drop_table("carriers")
