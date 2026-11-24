"""phase10f_cloud_sync_api

Revision ID: 7a8b9c0d1e2f
Revises: 3d6bec57fb10
Create Date: 2026-11-22 10:55:00.000000

Phase 10F: Cloud Backend & Synchronization API Foundation:
- Creates sync_operations table for monotonic cursor-based change tracking
- Creates sync_cursors table for per-device pull/push tracking
- Creates sync_entity_versions table for entity version resolution and tombstoning
- Dual-database compatible with SQLite and PostgreSQL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '3d6bec57fb10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create sync_operations table
    op.create_table(
        "sync_operations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("operation_uuid", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_uuid", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("operation_type", sa.String(16), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("client_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(16), nullable=False, server_default="APPLIED"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_sync_operations_id", "sync_operations", ["id"])
    op.create_index("ix_sync_operations_operation_uuid", "sync_operations", ["operation_uuid"], unique=True)
    op.create_index("ix_sync_operations_user_id", "sync_operations", ["user_id"])
    op.create_index("ix_sync_operations_device_uuid", "sync_operations", ["device_uuid"])
    op.create_index("ix_sync_operations_entity_type", "sync_operations", ["entity_type"])
    op.create_index("ix_sync_operations_entity_id", "sync_operations", ["entity_id"])
    op.create_index("ix_sync_operations_received_at", "sync_operations", ["received_at"])
    op.create_index("ix_sync_op_user_id_seq", "sync_operations", ["user_id", "id"])
    op.create_index("ix_sync_op_user_entity", "sync_operations", ["user_id", "entity_type", "entity_id"])
    op.create_index("ix_sync_op_user_device", "sync_operations", ["user_id", "device_uuid"])

    # 2. Create sync_cursors table
    op.create_table(
        "sync_cursors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_uuid", sa.String(64), nullable=False),
        sa.Column("last_pulled_cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_pushed_cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "device_uuid", name="uq_sync_cursor_user_device"),
    )
    op.create_index("ix_sync_cursors_user_id", "sync_cursors", ["user_id"])
    op.create_index("ix_sync_cursors_device_uuid", "sync_cursors", ["device_uuid"])
    op.create_index("ix_sync_cursor_lookup", "sync_cursors", ["user_id", "device_uuid"])

    # 3. Create sync_entity_versions table
    op.create_table(
        "sync_entity_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_modified_device", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_sync_entity_version_user_type_id"),
    )
    op.create_index("ix_sync_entity_versions_user_id", "sync_entity_versions", ["user_id"])
    op.create_index("ix_sync_entity_versions_entity_type", "sync_entity_versions", ["entity_type"])
    op.create_index("ix_sync_entity_versions_entity_id", "sync_entity_versions", ["entity_id"])
    op.create_index("ix_sync_entity_versions_is_deleted", "sync_entity_versions", ["is_deleted"])
    op.create_index("ix_sync_ev_lookup", "sync_entity_versions", ["user_id", "entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("sync_entity_versions")
    op.drop_table("sync_cursors")
    op.drop_table("sync_operations")
