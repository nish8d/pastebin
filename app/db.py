"""Database connection setup.

- `engine` holds the connection pool (one per process).
- `SessionLocal()` gives a Session: a unit of work you add/query/commit through.
- `get_session()` is a FastAPI dependency: one Session per request, always closed.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# pool_pre_ping: check a pooled connection is alive before using it, so the app
# survives a Postgres restart without throwing errors on the next request.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
