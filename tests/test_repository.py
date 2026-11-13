from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app import repository
from app.models import Paste
from tests.helpers import add_paste

HOUR = timedelta(hours=1)
PAST = timedelta(seconds=-1)


def test_get_live_returns_unexpired(db_session):
    add_paste(db_session, "live0001", expires_in=HOUR, content="hello")
    paste = repository.get_live_paste(db_session, "live0001")
    assert paste is not None and paste.content == "hello"


def test_get_live_hides_expired(db_session):
    add_paste(db_session, "dead0001", expires_in=PAST)
    assert repository.get_live_paste(db_session, "dead0001") is None


def test_delete_expired_removes_only_expired(db_session):
    add_paste(db_session, "dead0001", expires_in=PAST)
    add_paste(db_session, "dead0002", expires_in=PAST)
    add_paste(db_session, "live0001", expires_in=HOUR)
    assert repository.delete_expired(db_session) == 2
    assert db_session.get(Paste, "live0001") is not None
    assert db_session.get(Paste, "dead0001") is None


def test_delete_expired_is_idempotent(db_session):
    add_paste(db_session, "dead0001", expires_in=PAST)
    assert repository.delete_expired(db_session) == 1
    assert repository.delete_expired(db_session) == 0


def test_insert_duplicate_id_raises(db_session):
    add_paste(db_session, "same0001", expires_in=HOUR)
    now = datetime.now(UTC)
    with pytest.raises(IntegrityError):
        repository.insert_paste(
            db_session, paste_id="same0001", content="y", created_at=now, expires_at=now + HOUR
        )
