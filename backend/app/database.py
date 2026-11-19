from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

# Engine configuration
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
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
    import backend.app.models.goal  # noqa: F401
    import backend.app.models.task  # noqa: F401
    import backend.app.models.habit  # noqa: F401
    import backend.app.models.habit_log  # noqa: F401
    import backend.app.models.timeblock  # noqa: F401
    import backend.app.models.activity_log  # noqa: F401
    import backend.app.models.recommendation  # noqa: F401
    Base.metadata.create_all(bind=engine)
