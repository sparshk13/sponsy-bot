"""templates and brochures tables and message attachment foreign key

Revision ID: g7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "g7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('first', 'followup', 'meeting')", name="ck_templates_kind"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_templates_kind", "templates", ["kind"])

    op.create_table(
        "brochures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tier IN ('cash', 'goodies', 'credits')", name="ck_brochures_tier"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index("ix_brochures_tier", "brochures", ["tier"])

    op.create_foreign_key(
        "fk_messages_attachment_id",
        "messages",
        "brochures",
        ["attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_attachment_id", "messages", type_="foreignkey")
    op.drop_index("ix_brochures_tier", table_name="brochures")
    op.drop_table("brochures")
    op.drop_index("ix_templates_kind", table_name="templates")
    op.drop_table("templates")
