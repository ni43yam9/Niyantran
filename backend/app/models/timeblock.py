from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class DailyTimeblock(Base):
    __tablename__ = "daily_timeblocks"

    id = Column(String(36), primary_key=True, index=True)
    block_date = Column(Date, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    time = Column(String(20), nullable=False) # e.g. "09:00 AM"
    duration_minutes = Column(Integer, nullable=False, default=60) # Planned duration
    actual_duration_minutes = Column(Integer, nullable=True) # Actual duration (Planned vs Actual)
    category = Column(String(50), nullable=False, default="General")
    status = Column(String(20), nullable=False, default="Pending") # 'Pending', 'In Progress', 'Completed'
    is_break = Column(Boolean, nullable=False, default=False)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationship to Task
    task = relationship("Task")

    __table_args__ = (
        CheckConstraint("status IN ('Pending', 'In Progress', 'Completed')", name="check_timeblock_status"),
        Index("idx_timeblock_date_status", "block_date", "status"),
    )

    def __repr__(self):
        return f"<DailyTimeblock(id='{self.id}', date='{self.block_date}', title='{self.title}', status='{self.status}')>"
