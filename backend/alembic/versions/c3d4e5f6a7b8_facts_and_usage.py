"""facts and api usage

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-19 00:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_facts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('profile', 'past_sponsorship', 'other')",
            name="ck_company_facts_kind",
        ),
        sa.CheckConstraint(
            "status IN ('verified', 'unverified')",
            name="ck_company_facts_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_facts_company_id", "company_facts", ["company_id"], unique=False)
    op.create_index(
        "ix_company_facts_company_status",
        "company_facts",
        ["company_id", "status"],
        unique=False,
    )

    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "provider", name="uq_api_usage_day_provider"),
    )
    op.create_index("ix_api_usage_day", "api_usage", ["day"], unique=False)
    op.create_index("ix_api_usage_provider", "api_usage", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_usage_provider", table_name="api_usage")
    op.drop_index("ix_api_usage_day", table_name="api_usage")
    op.drop_table("api_usage")

    op.drop_index("ix_company_facts_company_status", table_name="company_facts")
    op.drop_index("ix_company_facts_company_id", table_name="company_facts")
    op.drop_table("company_facts")
