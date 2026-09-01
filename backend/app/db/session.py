"""Database engine and session handling."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set -- see .env.example")
        # pool_pre_ping: Supabase closes idle connections; this reconnects
        # instead of failing the first request after a quiet period.
        #
        # executemany_mode: without this, psycopg2 sends one round trip per
        # row. A people upload writes ~2,600 rows, which over a hosted
        # connection means ~2,600 round trips and a request that looks hung.
        # Batching folds them into a handful of multi-row statements.
        # On Vercel each request runs in a fresh function, so a pool would
        # hold connections that never get reused and would exhaust Supabase's
        # limit. NullPool opens and closes one connection per request instead.
        serverless = os.environ.get("VENMITO_SERVERLESS") == "1"
        pool_args = {"poolclass": NullPool} if serverless else {"pool_pre_ping": True}

        _engine = create_engine(
            settings.sqlalchemy_url,
            **pool_args,
            future=True,
            executemany_mode="values_plus_batch",
            executemany_batch_page_size=1000,
            connect_args={"connect_timeout": 15},
        )
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction per upload: a half-loaded file is worse than no file."""
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session


def healthcheck() -> bool:
    with get_engine().connect() as conn:
        return conn.execute(text("select 1")).scalar() == 1
