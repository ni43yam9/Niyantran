import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Boolean, Date, DateTime, CheckConstraint, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Goal(Base):
    __tablename__ = "goals"

    id = Column(String(50), primary_key=True, index=True, default=lambda: f"gol_{uuid.uuid4().hex}")
    user_id = Column(String(50), nullable=False, default="default_user", index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    goal_type = Column(String(50), nullable=False, default="Short-Term")  # 'Short-Term', 'Long-Term'
    category = Column(String(50), nullable=False, default="Coding")
    priority = Column(String(20), nullable=False, default="Medium")       # 'High', 'Medium', 'Low'
    status = Column(String(20), nullable=False, default="In Progress")    # 'In Progress', 'On Track', 'Behind', 'Completed'
    start_date = Column(Date, nullable=False)
    target_date = Column(Date, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    key_milestone = Column(String(255), nullable=True)
    
    # Synchronization & Soft Deletion Fields
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    tasks = relationship("Task", back_populates="goal", cascade="save-update, merge")

    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="check_goal_progress_range"),
        CheckConstraint("goal_type IN ('Short-Term', 'Long-Term')", name="check_goal_type"),
        CheckConstraint("priority IN ('High', 'Medium', 'Low')", name="check_goal_priority"),
        CheckConstraint("status IN ('In Progress', 'On Track', 'Behind', 'Completed')", name="check_goal_status"),
        Index("idx_goals_type_status", "goal_type", "status"),
        Index("idx_goals_target_date", "target_date"),
        Index("idx_goals_is_deleted", "is_deleted"),
        Index("idx_goals_sync", "user_id", "version", "updated_at"),
    )

    def __repr__(self):
        return f"<Goal(id='{self.id}', title='{self.title}', type='{self.goal_type}', progress={self.progress})>"
