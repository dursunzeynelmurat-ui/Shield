import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment if set
db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql+psycopg2://")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Import all models so Alembic can detect them
from app.database import Base
import app.models  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Use async engine but run migrations synchronously via run_sync
    from sqlalchemy.ext.asyncio import create_async_engine
    url = config.get_main_option("sqlalchemy.url")
    # For migration we use psycopg2 sync driver
    sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    from sqlalchemy import create_engine
    connectable = create_engine(sync_url)
    with connectable.connect() as connection:
        do_run_migrations(connection)


def run_migrations_online() -> None:
    import sqlalchemy as sa
    url = config.get_main_option("sqlalchemy.url")
    sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    connectable = sa.create_engine(sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
