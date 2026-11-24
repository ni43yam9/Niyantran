import uuid
import logging
from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.models.daily_intent import DailyIntent
from backend.app.schemas.daily_intent import DailyIntentCreate, DailyIntentUpdate

logger = logging.getLogger("niyantra.daily_intent")

def get_daily_intent_by_date(
    db: Session,
    intent_date: date,
    user_id: str = "default_user",
    include_deleted: bool = False,
) -> Optional[DailyIntent]:
    """Retrieves the active daily intent for a specific date and user."""
    query = db.query(DailyIntent).filter(
        DailyIntent.user_id == user_id,
        DailyIntent.intent_date == intent_date,
    )
    if not include_deleted:
        query = query.filter(DailyIntent.is_deleted == False)
    return query.first()

def get_daily_intent_by_id(
    db: Session,
    intent_id: str,
    include_deleted: bool = False,
) -> Optional[DailyIntent]:
    """Retrieves a daily intent by its unique ID."""
    query = db.query(DailyIntent).filter(DailyIntent.id == intent_id)
    if not include_deleted:
        query = query.filter(DailyIntent.is_deleted == False)
    return query.first()

def list_daily_intents(
    db: Session,
    user_id: str = "default_user",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
) -> List[DailyIntent]:
    """Lists non-deleted daily intents sorted by date descending."""
    query = db.query(DailyIntent).filter(
        DailyIntent.user_id == user_id,
        DailyIntent.is_deleted == False,
    )
    if start_date:
        query = query.filter(DailyIntent.intent_date >= start_date)
    if end_date:
        query = query.filter(DailyIntent.intent_date <= end_date)
    return query.order_by(DailyIntent.intent_date.desc()).limit(limit).all()

def upsert_daily_intent(
    db: Session,
    intent_in: DailyIntentCreate,
) -> DailyIntent:
    """
    Creates or updates a daily intent directive for the target date.
    Enforces uniqueness per user_id + intent_date.
    Increments version on update for synchronization readiness.
    """
    user_id = intent_in.user_id or "default_user"
    now_utc = datetime.now(timezone.utc)

    existing = db.query(DailyIntent).filter(
        DailyIntent.user_id == user_id,
        DailyIntent.intent_date == intent_in.intent_date,
    ).first()

    if existing:
        existing.intent_text = intent_in.intent_text
        existing.is_deleted = False
        existing.deleted_at = None
        existing.version += 1
        existing.updated_at = now_utc
        db.commit()
        db.refresh(existing)
        return existing

    new_intent = DailyIntent(
        id=f"int_{uuid.uuid4().hex}",
        user_id=user_id,
        intent_date=intent_in.intent_date,
        intent_text=intent_in.intent_text,
        version=1,
        is_deleted=False,
        deleted_at=None,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(new_intent)
    db.commit()
    db.refresh(new_intent)
    return new_intent

def update_daily_intent(
    db: Session,
    intent_id: str,
    update_in: DailyIntentUpdate,
) -> Optional[DailyIntent]:
    """Updates an existing intent's text and increments version."""
    intent = get_daily_intent_by_id(db, intent_id)
    if not intent:
        return None

    now_utc = datetime.now(timezone.utc)
    intent.intent_text = update_in.intent_text
    intent.version += 1
    intent.updated_at = now_utc
    db.commit()
    db.refresh(intent)
    return intent

def soft_delete_daily_intent(
    db: Session,
    intent_date: date,
    user_id: str = "default_user",
) -> bool:
    """
    Soft-deletes a daily intent by marking is_deleted=True and setting deleted_at.
    Increments version for tombstone synchronization.
    """
    intent = get_daily_intent_by_date(db, intent_date, user_id=user_id)
    if not intent:
        return False

    now_utc = datetime.now(timezone.utc)
    intent.is_deleted = True
    intent.deleted_at = now_utc
    intent.version += 1
    intent.updated_at = now_utc
    db.commit()
    return True
