from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class SyncOperation(Base):
    """
    Append-only log of synchronization operations processed by the cloud backend.
    
    The auto-incrementing integer `id` acts as the monotonic logical clock (cursor)
    for pull pagination across multi-device clients.
    `operation_uuid` provides client-generated idempotency tokens.
    """
    __tablename__ = "sync_operations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    operation_uuid = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_uuid = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # task, goal, habit, habit_log, etc.
    entity_id = Column(String(64), nullable=False, index=True)
    operation_type = Column(String(16), nullable=False)  # CREATE, UPDATE, DELETE
    entity_version = Column(Integer, nullable=False, default=1)
    payload = Column(JSON, nullable=True)
    client_created_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    status = Column(String(16), nullable=False, default="APPLIED")  # APPLIED, REJECTED, CONFLICT, SUPERSEDED
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sync_operations")

    __table_args__ = (
        Index("ix_sync_op_user_id_seq", "user_id", "id"),
        Index("ix_sync_op_user_entity", "user_id", "entity_type", "entity_id"),
        Index("ix_sync_op_user_device", "user_id", "device_uuid"),
    )

    def __repr__(self) -> str:
        return (
            f"<SyncOperation id={self.id} uuid={self.operation_uuid} user={self.user_id} "
            f"device={self.device_uuid} type={self.operation_type} entity={self.entity_type}:{self.entity_id} "
            f"ver={self.entity_version} status={self.status}>"
        )


class SyncCursor(Base):
    """
    Maintains per-device synchronization checkpoints for each registered client device.
    
    Tracks the highest monotonic sequence ID (`last_pulled_cursor` and `last_pushed_cursor`)
    successfully processed by the device.
    """
    __tablename__ = "sync_cursors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_uuid = Column(String(64), nullable=False, index=True)
    last_pulled_cursor = Column(Integer, nullable=False, default=0)
    last_pushed_cursor = Column(Integer, nullable=False, default=0)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="sync_cursors")

    __table_args__ = (
        UniqueConstraint("user_id", "device_uuid", name="uq_sync_cursor_user_device"),
        Index("ix_sync_cursor_lookup", "user_id", "device_uuid"),
    )

    def __repr__(self) -> str:
        return (
            f"<SyncCursor id={self.id} user={self.user_id} device={self.device_uuid} "
            f"pulled={self.last_pulled_cursor} pushed={self.last_pushed_cursor}>"
        )


class SyncEntityVersion(Base):
    """
    Tracks canonical server-side version numbers for every productivity entity per user.
    Used for conflict detection, stale change superseding, and tombstone tracking.
    """
    __tablename__ = "sync_entity_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    current_version = Column(Integer, nullable=False, default=1)
    last_modified_device = Column(String(64), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="sync_entity_versions")

    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_sync_entity_version_user_type_id"),
        Index("ix_sync_ev_lookup", "user_id", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SyncEntityVersion id={self.id} user={self.user_id} entity={self.entity_type}:{self.entity_id} "
            f"ver={self.current_version} del={self.is_deleted}>"
        )


class SyncConflict(Base):
    """
    Tracks synchronization conflicts detected and resolved across multi-device clients.
    Provides server-side auditability, tenant isolation, and conflict state verification.
    """
    __tablename__ = "sync_conflicts"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    base_version = Column(Integer, nullable=False, default=1)
    local_version = Column(Integer, nullable=False, default=1)
    remote_version = Column(Integer, nullable=False, default=1)
    detecting_device_uuid = Column(String(64), nullable=False)
    conflicting_device_uuid = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="PENDING_RESOLUTION", index=True)
    resolution_strategy = Column(String(32), nullable=True)
    local_data = Column(JSON, nullable=True)
    remote_data = Column(JSON, nullable=True)
    resolved_data = Column(JSON, nullable=True)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sync_conflicts")

    __table_args__ = (
        Index("ix_sync_conflicts_lookup", "user_id", "status"),
        Index("ix_sync_conflicts_entity_lookup", "user_id", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SyncConflict id={self.id} user={self.user_id} entity={self.entity_type}:{self.entity_id} "
            f"status={self.status} strategy={self.resolution_strategy}>"
        )
