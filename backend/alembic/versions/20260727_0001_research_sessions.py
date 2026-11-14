"""Create research sessions and event ledger.

Revision ID: 20260727_0001
Revises:
Create Date: 2026-07-27
"""

import sqlalchemy as sa

from alembic import op

revision = "20260727_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(length=240), nullable=False),
        sa.Column("normalized_query", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("research_plan", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_sessions_normalized_query", "research_sessions", ["normalized_query"]
    )
    op.create_index("ix_research_sessions_status", "research_sessions", ["status"])
    op.create_table(
        "research_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("research_session_id", "sequence", name="uq_event_sequence"),
    )
    op.create_index(
        "ix_research_events_research_session_id", "research_events", ["research_session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_research_events_research_session_id", table_name="research_events")
    op.drop_table("research_events")
    op.drop_index("ix_research_sessions_status", table_name="research_sessions")
    op.drop_index("ix_research_sessions_normalized_query", table_name="research_sessions")
    op.drop_table("research_sessions")
