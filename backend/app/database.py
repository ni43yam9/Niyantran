from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

# Engine configuration
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine_kwargs = {"echo": False}
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 15,  # 15s driver-level busy timeout for concurrent transactions
    }
else:
    # Production cloud connection pooling for PostgreSQL
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(
    db_url,
    **engine_kwargs,
)

from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def get_db():
    """
    Dependency that yields a database session per request.
    Ensures safe commit/rollback and closes the session cleanly.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """
    Creates all database tables defined on Base if they do not exist.
    """
    import backend.app.models.user  # noqa: F401
    import backend.app.models.device  # noqa: F401
    import backend.app.models.goal  # noqa: F401
    import backend.app.models.task  # noqa: F401
    import backend.app.models.habit  # noqa: F401
    import backend.app.models.habit_log  # noqa: F401
    import backend.app.models.timeblock  # noqa: F401
    import backend.app.models.activity_log  # noqa: F401
    import backend.app.models.recommendation  # noqa: F401
    import backend.app.models.predictive_insight  # noqa: F401
    import backend.app.models.adaptive_profile  # noqa: F401
    import backend.app.models.daily_intent  # noqa: F401
    import backend.app.models.sync  # noqa: F401
    Base.metadata.create_all(bind=engine)
