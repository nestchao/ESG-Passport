"""Alembic migration environment. DATABASE_URL is never logged."""
from logging.config import fileConfig
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from esg_backend.db import build_engine
from esg_backend.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
load_dotenv()
target_metadata = Base.metadata


def migration_url():
    value = os.getenv('DATABASE_URL') or config.get_main_option('sqlalchemy.url')
    if not value:
        raise ValueError('Set DATABASE_URL before running Alembic migrations.')
    parsed = make_url(value)
    if parsed.drivername in ('postgres', 'postgresql', 'postgresql+psycopg'):
        parsed = parsed.set(drivername='postgresql+psycopg')
        if 'sslmode' not in parsed.query:
            parsed = parsed.update_query_dict({'sslmode': 'require'})
    return parsed


def run_migrations_offline():
    context.configure(url=migration_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied = config.attributes.get('connection')
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = build_engine(migration_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
