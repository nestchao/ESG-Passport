"""Explicit engine/session construction; startup never creates or seeds tables."""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker


def build_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.drivername in ('postgres', 'postgresql', 'postgresql+psycopg'):
        parsed = parsed.set(drivername='postgresql+psycopg')
        if 'sslmode' not in parsed.query:
            parsed = parsed.update_query_dict({'sslmode': 'require'})
        return create_engine(parsed, pool_pre_ping=True)
    if parsed.drivername.startswith('sqlite'):
        # SQLite is reserved for explicit dependency injection in tests.
        return create_engine(parsed, connect_args={'check_same_thread': False})
    raise ValueError('Use a Postgres URL with the Psycopg 3 driver.')


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
