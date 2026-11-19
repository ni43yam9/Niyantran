from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Date, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(String(36), primary_key=True, index=True)
    habit_id = Column(String(36), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    log_date = Column(Date, nullable=False, index=True)
    completed = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=utc_now)

    # Relationships
    habit = relationship("Habit", back_populates="logs")

    __table_args__ = (
        UniqueConstraint("habit_id", "log_date", name="uq_habit_date"),
        Index("idx_habit_logs_date", "log_date"),
    )

    def __repr__(self):
        return f"<HabitLog(habit_id='{self.habit_id}', date='{self.log_date}', completed={self.completed})>"
