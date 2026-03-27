"""Add chat_sessions table and session_id to query_executions

Revision ID: 005
Revises: 004
Create Date: 2026-03-27

Adds chat_sessions table for ChatGPT-style threaded conversations.
Each session belongs to a connection and has an auto-title (set from
the first question). QueryExecution rows gain a nullable session_id FK
so messages can be grouped into threads.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("database_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(100), nullable=False, server_default="New Chat"),
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
    )
    op.create_index("ix_chat_sessions_connection_id", "chat_sessions", ["connection_id"])
    op.create_index("ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"])

    op.add_column(
        "query_executions",
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_query_executions_session_id", "query_executions", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_query_executions_session_id", "query_executions")
    op.drop_column("query_executions", "session_id")
    op.drop_index("ix_chat_sessions_updated_at", "chat_sessions")
    op.drop_index("ix_chat_sessions_connection_id", "chat_sessions")
    op.drop_table("chat_sessions")
