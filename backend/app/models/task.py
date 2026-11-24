import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Date, DateTime, Boolean, Integer, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(50), primary_key=True, index=True, default=lambda: f"tsk_{uuid.uuid4().hex}")
    user_id = Column(String(50), nullable=False, default="default_user", index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False, default="Daily")      # 'Daily', 'Short-Term', 'Long-Term', 'One-Time', 'Occasional'
    category = Column(String(50), nullable=False, default="Coding")      # 'Academic', 'Coding', 'Career', 'Reading', 'Health', 'Personal'
    priority = Column(String(20), nullable=False, default="Medium")      # 'High', 'Medium', 'Low'
    status = Column(String(20), nullable=False, default="Pending")       # 'Pending', 'In Progress', 'Completed'
    start_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    goal_id = Column(String(50), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Synchronization & Soft Deletion Fields
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationship
    goal = relationship("Goal", back_populates="tasks")

    __table_args__ = (
        CheckConstraint("task_type IN ('Daily', 'Short-Term', 'Long-Term', 'One-Time', 'Occasional')", name="check_task_type"),
        CheckConstraint("category IN ('Academic', 'Coding', 'Career', 'Reading', 'Health', 'Personal')", name="check_task_category"),
        CheckConstraint("priority IN ('High', 'Medium', 'Low')", name="check_task_priority"),
        CheckConstraint("status IN ('Pending', 'In Progress', 'Completed')", name="check_task_status"),
        Index("idx_tasks_status_due", "status", "due_date"),
        Index("idx_tasks_status_completed", "status", "completed_at"),
        Index("idx_tasks_completed_at", "completed_at"),
        Index("idx_tasks_type", "task_type"),
        Index("idx_tasks_priority", "priority"),
        Index("idx_tasks_is_deleted", "is_deleted"),
        Index("idx_tasks_sync", "user_id", "version", "updated_at"),
    )

    def __repr__(self):
        return f"<Task(id='{self.id}', title='{self.title}', status='{self.status}', priority='{self.priority}')>"
