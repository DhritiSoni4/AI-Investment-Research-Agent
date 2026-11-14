"""Add structured agent artifacts.

Revision ID: 20260727_0002
Revises: 20260727_0001
Create Date: 2026-07-27
"""

import sqlalchemy as sa

from alembic import op

revision = "20260727_0002"
down_revision = "20260727_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_session_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["research_session_id"], ["research_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_session_id", "agent_name", name="uq_agent_artifact"),
    )
    op.create_index(
        "ix_agent_artifacts_research_session_id", "agent_artifacts", ["research_session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_artifacts_research_session_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
