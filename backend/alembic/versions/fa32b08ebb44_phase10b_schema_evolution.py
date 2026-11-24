"""phase10b_schema_evolution

Revision ID: fa32b08ebb44
Revises: 
Create Date: 2026-11-21 20:29:26.409061

Non-breaking database schema evolution for future offline-first, multi-device synchronization:
- Introduces default user ownership ('default_user') across synchronized entities
- Introduces version counters for change tracking
- Introduces soft-delete metadata (is_deleted, deleted_at)
- Adds updated_at where missing (habit_logs)
- Introduces user_id and device_id for append-only activity_logs
- Creates daily_intents table
- Fully reversible with SQLite batch mode support
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa32b08ebb44'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create daily_intents table
    op.create_table(
        "daily_intents",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"),
        sa.Column("intent_date", sa.Date(), nullable=False),
        sa.Column("intent_text", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "intent_date", name="uq_user_intent_date"),
    )
    op.create_index("ix_daily_intent_user_date", "daily_intents", ["user_id", "intent_date"])
    op.create_index("ix_daily_intent_sync", "daily_intents", ["user_id", "version", "updated_at"])

    # 2. tasks: add user_id, version, is_deleted, deleted_at
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index("idx_tasks_is_deleted", ["is_deleted"])
        batch_op.create_index("idx_tasks_sync", ["user_id", "version", "updated_at"])

    # 3. goals: add user_id, version, is_deleted, deleted_at
    with op.batch_alter_table("goals") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index("idx_goals_is_deleted", ["is_deleted"])
        batch_op.create_index("idx_goals_sync", ["user_id", "version", "updated_at"])

    # 4. habits: add user_id, version, is_deleted, deleted_at
    with op.batch_alter_table("habits") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index("idx_habits_is_deleted", ["is_deleted"])
        batch_op.create_index("idx_habits_sync", ["user_id", "version", "updated_at"])

    # 5. habit_logs: add user_id, version, is_deleted, deleted_at, updated_at
    with op.batch_alter_table("habit_logs") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
        batch_op.create_index("idx_habit_logs_is_deleted", ["is_deleted"])
        batch_op.create_index("idx_habit_logs_sync", ["user_id", "version", "updated_at"])

    # 6. daily_timeblocks: add user_id, version, is_deleted, deleted_at
    with op.batch_alter_table("daily_timeblocks") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index("idx_timeblock_is_deleted", ["is_deleted"])
        batch_op.create_index("idx_timeblock_sync", ["user_id", "version", "updated_at"])

    # 7. recommendations: add user_id, version, is_deleted, deleted_at
    with op.batch_alter_table("recommendations") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_recommendation_is_deleted", ["is_deleted"])
        batch_op.create_index("ix_recommendation_sync", ["user_id", "version", "updated_at"])

    # 8. activity_logs: add user_id, device_id
    with op.batch_alter_table("activity_logs") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(50), nullable=False, server_default="default_user"))
        batch_op.add_column(sa.Column("device_id", sa.String(50), nullable=True, server_default="local_device"))
        batch_op.create_index("ix_activity_user_time", ["user_id", "timestamp"])


def downgrade() -> None:
    # 8. activity_logs
    with op.batch_alter_table("activity_logs") as batch_op:
        batch_op.drop_index("ix_activity_user_time")
        batch_op.drop_column("device_id")
        batch_op.drop_column("user_id")

    # 7. recommendations
    with op.batch_alter_table("recommendations") as batch_op:
        batch_op.drop_index("ix_recommendation_sync")
        batch_op.drop_index("ix_recommendation_is_deleted")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("version")
        batch_op.drop_column("user_id")

    # 6. daily_timeblocks
    with op.batch_alter_table("daily_timeblocks") as batch_op:
        batch_op.drop_index("idx_timeblock_sync")
        batch_op.drop_index("idx_timeblock_is_deleted")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("version")
        batch_op.drop_column("user_id")

    # 5. habit_logs
    with op.batch_alter_table("habit_logs") as batch_op:
        batch_op.drop_index("idx_habit_logs_sync")
        batch_op.drop_index("idx_habit_logs_is_deleted")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("version")
        batch_op.drop_column("user_id")

    # 4. habits
    with op.batch_alter_table("habits") as batch_op:
        batch_op.drop_index("idx_habits_sync")
        batch_op.drop_index("idx_habits_is_deleted")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("version")
        batch_op.drop_column("user_id")

    # 3. goals
    with op.batch_alter_table("goals") as batch_op:
        batch_op.drop_index("idx_goals_sync")
        batch_op.drop_index("idx_goals_is_deleted")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("version")
        batch_op.drop_column("user_id")

    # 2. tasks
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index("idx_tasks_sync")
        batch_op.drop_index("idx_tasks_is_deleted")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
        batch_op.drop_column("version")
        batch_op.drop_column("user_id")

    # 1. daily_intents
    op.drop_index("ix_daily_intent_sync", table_name="daily_intents")
    op.drop_index("ix_daily_intent_user_date", table_name="daily_intents")
    op.drop_table("daily_intents")
