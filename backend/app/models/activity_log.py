import uuid
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, Date, DateTime, JSON, Index
from backend.app.database import Base

class ActivityLog(Base):
    """
    Records meaningful user actions and productivity events for behaviour monitoring.
    Events include task lifecycle, habit completions, postponements, and timeblock execution.
    """
    __tablename__ = "activity_logs"

    id = Column(String(50), primary_key=True, default=lambda: f"act_{uuid.uuid4().hex[:12]}")
    event_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(30), nullable=False, index=True)  # 'task', 'habit', 'timeblock', 'plan'
    entity_id = Column(String(100), nullable=True, index=True)
    
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Event-specific contextual metadata
    original_date = Column(Date, nullable=True)
    new_date = Column(Date, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    actual_duration_minutes = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_activity_entity", "entity_type", "entity_id"),
        Index("ix_activity_type_time", "event_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ActivityLog {self.id}: {self.event_type} on {self.entity_type}:{self.entity_id}>"
