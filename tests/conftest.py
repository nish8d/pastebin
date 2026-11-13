"""Shared pytest fixtures.

Tests run against a real PostgreSQL (a throwaway Docker container on port 5443),
not SQLite, so that things like `now()` and timezone handling behave exactly as
they will in production. See README.md for the `docker run` command.
"""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://pastebin:pastebin@127.0.0.1:5443/pastebin_test",
)
# Must be set before anything imports app.db (which builds the engine from settings).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.models import Base, Paste  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(Paste))
        session.commit()
        session.close()


@pytest.fixture
def client(db_session):
    """An HTTP test client whose requests use the test's db_session."""
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
