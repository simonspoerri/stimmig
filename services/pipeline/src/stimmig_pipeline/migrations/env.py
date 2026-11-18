"""Alembic environment. Migrations run via ``stimmig_pipeline.db.migrate``."""

from alembic import context
from sqlalchemy import create_engine

from stimmig_pipeline.models import Base

config = context.config


def run_migrations_online() -> None:
    engine = create_engine(config.get_main_option("sqlalchemy.url") or "")
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
