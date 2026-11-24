import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Date, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(String(50), primary_key=True, index=True, default=lambda: f"hlg_{uuid.uuid4().hex}")
    user_id = Column(String(50), nullable=False, default="default_user", index=True)
    habit_id = Column(String(50), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    log_date = Column(Date, nullable=False, index=True)
    completed = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    
    # Synchronization & Soft Deletion Fields
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    habit = relationship("Habit", back_populates="logs")

    __table_args__ = (
        UniqueConstraint("habit_id", "log_date", name="uq_habit_date"),
        Index("idx_habit_logs_date", "log_date"),
        Index("idx_habit_logs_completed_date", "completed", "log_date"),
        Index("idx_habit_logs_is_deleted", "is_deleted"),
        Index("idx_habit_logs_sync", "user_id", "version", "updated_at"),
    )

    def __repr__(self):
        return f"<HabitLog(habit_id='{self.habit_id}', date='{self.log_date}', completed={self.completed})>"
