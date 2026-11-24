"""phase10h_conflict_management

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-11-22 15:35:00.000000

Phase 10H: Conflict Detection & Resolution Server Foundation
- Creates sync_conflicts table for server-side conflict tracking and multi-device auditability
- Enforces strict tenant isolation and foreign key constraints
- Dual-database compatible with SQLite and PostgreSQL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_conflicts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("local_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("remote_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("detecting_device_uuid", sa.String(64), nullable=False),
        sa.Column("conflicting_device_uuid", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING_RESOLUTION"),
        sa.Column("resolution_strategy", sa.String(32), nullable=True),
        sa.Column("local_data", sa.JSON(), nullable=True),
        sa.Column("remote_data", sa.JSON(), nullable=True),
        sa.Column("resolved_data", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sync_conflicts_id", "sync_conflicts", ["id"])
    op.create_index("ix_sync_conflicts_user_id", "sync_conflicts", ["user_id"])
    op.create_index("ix_sync_conflicts_entity_type", "sync_conflicts", ["entity_type"])
    op.create_index("ix_sync_conflicts_entity_id", "sync_conflicts", ["entity_id"])
    op.create_index("ix_sync_conflicts_status", "sync_conflicts", ["status"])
    op.create_index("ix_sync_conflicts_lookup", "sync_conflicts", ["user_id", "status"])
    op.create_index("ix_sync_conflicts_entity_lookup", "sync_conflicts", ["user_id", "entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("sync_conflicts")
