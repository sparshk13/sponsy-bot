"""campaigns, companies, contacts, targets, and messages

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-18 12:35:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("event_summary", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("audience_note", sa.Text(), nullable=True),
        sa.Column("cash_target_inr", sa.Integer(), nullable=True),
        sa.Column("goodies_note", sa.Text(), nullable=True),
        sa.Column("credits_note", sa.Text(), nullable=True),
        sa.Column("calendar_link", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("first_added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=True)
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])

    op.create_table(
        "targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="not_contacted"),
        sa.Column("tier", sa.String(length=32), nullable=True),
        sa.Column("priority", sa.String(length=8), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ask_summary", sa.Text(), nullable=True),
        sa.Column("ask_reasoning", sa.Text(), nullable=True),
        sa.Column("ask_fact_ids", sa.JSON(), nullable=True),
        sa.Column("ask_basis", sa.String(length=32), nullable=True),
        sa.Column("followup_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cooldown_unlocked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('not_contacted', 'contacted', 'follow_up', 'interested', "
            "'meeting_booked', 'secured', 'declined', 'closed_no_reply')",
            name="ck_targets_status",
        ),
        sa.CheckConstraint(
            "tier IS NULL OR tier IN ('cash', 'goodies', 'credits')", name="ck_targets_tier"
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority IN ('A', 'B', 'C')", name="ck_targets_priority"
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "company_id", name="uq_targets_campaign_company"),
    )
    op.create_index("ix_targets_campaign_id", "targets", ["campaign_id"])
    op.create_index("ix_targets_company_id", "targets", ["company_id"])
    op.create_index("ix_targets_owner_id", "targets", ["owner_id"])
    op.create_index("ix_targets_campaign_status", "targets", ["campaign_id", "status"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("facts_used", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_hash", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_id_header", sa.String(length=255), nullable=True),
        sa.Column("in_reply_to", sa.String(length=255), nullable=True),
        sa.Column("attachment_id", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("suggested_reply", sa.Text(), nullable=True),
        sa.Column(
            "classified_by_human", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction IN ('out', 'in')", name="ck_messages_direction"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'sent', 'failed', 'discarded', 'received')",
            name="ck_messages_status",
        ),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_target_id", "messages", ["target_id"])
    op.create_index(
        "one_inflight_per_target",
        "messages",
        ["target_id"],
        unique=True,
        postgresql_where=sa.text("direction = 'out' AND status IN ('draft', 'approved')"),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("targets")
    op.drop_table("contacts")
    op.drop_table("companies")
    op.drop_table("campaigns")
