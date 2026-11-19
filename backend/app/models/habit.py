from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Habit(Base):
    __tablename__ = "habits"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    target = Column(String(100), nullable=True)
    category = Column(String(50), nullable=False, default="General")
    frequency = Column(String(50), nullable=False, default="Daily")
    base_streak = Column(Integer, nullable=False, default=0)
    archived = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # 1-to-many relationship with habit logs
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan", lazy="joined")

    def __repr__(self):
        return f"<Habit(id='{self.id}', name='{self.name}', streak={self.base_streak})>"
