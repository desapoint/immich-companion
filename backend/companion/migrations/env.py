"""Alembic environment for companion-owned tables."""

from alembic import context
from sqlalchemy import create_engine, pool

from companion.models import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    value = config.attributes.get("database_url")
    if not isinstance(value, str) or not value:
        raise RuntimeError("Alembic database URL was not supplied")
    return value


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""

    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a short-lived synchronous psycopg engine."""

    connectable = create_engine(database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
