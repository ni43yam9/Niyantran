import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from backend.app.database import Base


class Device(Base):
    """
    Device Model for NIYANTRA.
    Tracks client device identities registered to a user account for multi-device synchronization.
    """
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String(128), nullable=False)
    device_type = Column(String(32), default="Laptop", nullable=False)  # 'Laptop', 'Mobile', 'Tablet', 'Desktop', 'Other'
    operating_system = Column(String(64), default="Unknown", nullable=False)
    client_version = Column(String(32), nullable=True, default="2.0.0")
    registered_at = Column(DateTime, default=func.now(), nullable=False)
    last_active_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String(32), default="active", nullable=False)  # 'active', 'revoked'
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="devices")

    __table_args__ = (
        Index("ix_device_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Device id={self.id} user_id={self.user_id} name={self.device_name} status={self.status}>"
