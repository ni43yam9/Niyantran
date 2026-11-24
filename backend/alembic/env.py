import sys
from logging.config import fileConfig
from pathlib import Path
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure workspace root and backend are in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.core.config import settings
from backend.app.database import Base
# Import all models for Alembic metadata
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

config = context.config

# Dynamically set sqlalchemy.url from our application settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
