"""phase10c_auth_and_devices

Revision ID: 3d6bec57fb10
Revises: fa32b08ebb44
Create Date: 2026-11-22 00:12:20.335988

Phase 10C: Authentication and Device Management schema:
- Creates users table for multi-device user accounts
- Seeds default local user ('default_user') ensuring foreign-key and ownership consistency with Phase 10B
- Creates devices table for client device identity tracking
- Provides full reversible downgrade logic with SQLite batch compatibility
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d6bec57fb10'
down_revision: Union[str, Sequence[str], None] = 'fa32b08ebb44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_uuid", "users", ["uuid"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Seed default local user ('default_user') to anchor all Phase 10B backfilled records
    default_pwd_hash = "$2b$12$Vj0tRfEaEagh77f2UpM0fOQQWi0EyCKZptEh.WcWGSBZ5IOVAPazm"
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "sqlite"
    if dialect_name == "sqlite":
        op.execute(
            f"""
            INSERT OR IGNORE INTO users (id, uuid, name, email, password_hash, is_active, status, created_at, updated_at)
            VALUES (
                'default_user',
                '00000000-0000-0000-0000-000000000000',
                'Default User',
                'default@niyantra.local',
                '{default_pwd_hash}',
                1,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        )
    else:
        op.execute(
            f"""
            INSERT INTO users (id, uuid, name, email, password_hash, is_active, status, created_at, updated_at)
            VALUES (
                'default_user',
                '00000000-0000-0000-0000-000000000000',
                'Default User',
                'default@niyantra.local',
                '{default_pwd_hash}',
                true,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (id) DO NOTHING
            """
        )

    # 3. Create devices table
    op.create_table(
        "devices",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("device_uuid", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_name", sa.String(128), nullable=False),
        sa.Column("device_type", sa.String(32), nullable=False, server_default="Laptop"),
        sa.Column("operating_system", sa.String(64), nullable=False, server_default="Unknown"),
        sa.Column("client_version", sa.String(32), nullable=True, server_default="2.0.0"),
        sa.Column("registered_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_devices_device_uuid", "devices", ["device_uuid"], unique=True)
    op.create_index("ix_devices_user_id", "devices", ["user_id"])
    op.create_index("ix_device_user_status", "devices", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_device_user_status", table_name="devices")
    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_index("ix_devices_device_uuid", table_name="devices")
    op.drop_table("devices")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_uuid", table_name="users")
    op.drop_table("users")
