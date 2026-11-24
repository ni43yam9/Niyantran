import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Text, Date, DateTime, Boolean, Integer, UniqueConstraint, Index
from backend.app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class DailyIntent(Base):
    """
    Stores daily primary intent directives.
    Migrated from frontend localStorage into persistent database storage.
    Enforces uniqueness per user_id and intent_date for multi-device synchronization.
    """
    __tablename__ = "daily_intents"

    id = Column(String(50), primary_key=True, default=lambda: f"int_{uuid.uuid4().hex}")
    user_id = Column(String(50), nullable=False, default="default_user", index=True)
    intent_date = Column(Date, nullable=False, index=True)
    intent_text = Column(Text, nullable=False)

    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "intent_date", name="uq_user_intent_date"),
        Index("ix_daily_intent_user_date", "user_id", "intent_date"),
        Index("ix_daily_intent_sync", "user_id", "version", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<DailyIntent(user_id='{self.user_id}', date='{self.intent_date}', ver={self.version})>"
