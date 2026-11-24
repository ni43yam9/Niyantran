import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from backend.app.database import Base


class User(Base):
    """
    User Account model for NIYANTRA.
    Represents an authenticated user identity across multi-device clients.
    """
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), default="active", nullable=False)  # 'active', 'suspended', 'deactivated'
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    sync_operations = relationship("SyncOperation", back_populates="user", cascade="all, delete-orphan")
    sync_cursors = relationship("SyncCursor", back_populates="user", cascade="all, delete-orphan")
    sync_entity_versions = relationship("SyncEntityVersion", back_populates="user", cascade="all, delete-orphan")
    sync_conflicts = relationship("SyncConflict", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} status={self.status}>"
