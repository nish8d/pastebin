import re
from datetime import timedelta

import pytest

from app import service
from tests.helpers import add_paste


def test_generate_id_shape():
    for _ in range(50):
        assert re.fullmatch(r"[A-Za-z0-9]{8}", service.generate_id())


def test_ttl_options():
    assert list(service.TTLS) == ["1m", "10m", "1h", "1d", "1w"]
    assert service.TTLS["1w"] == timedelta(days=7)
    assert list(service.TTL_LABELS.values()) == ["1 minute", "10 minutes", "1 hour", "1 day", "1 week"]


def test_create_paste_sets_expiry(db_session):
    paste = service.create_paste(db_session, "hello", "1h")
    assert paste.expires_at - paste.created_at == timedelta(hours=1)


def test_create_preserves_whitespace(db_session):
    paste = service.create_paste(db_session, "  a\n\n", "1m")
    db_session.expunge_all()
    assert service.get_paste(db_session, paste.id).content == "  a\n\n"


def test_empty_content_rejected(db_session):
    with pytest.raises(service.EmptyContent):
        service.create_paste(db_session, "   \n", "1h")


def test_invalid_ttl_rejected(db_session):
    with pytest.raises(service.InvalidTTL):
        service.create_paste(db_session, "hi", "99y")


def test_too_large_bytes(db_session):
    # 262145 "é" characters is under the limit in characters but 524290 bytes in UTF-8.
    with pytest.raises(service.ContentTooLarge):
        service.create_paste(db_session, "é" * 262145, "1h")
    assert service.create_paste(db_session, "a" * 524288, "1h") is not None


def test_id_collision_retries(db_session, monkeypatch):
    add_paste(db_session, "dupdup12", expires_in=timedelta(hours=1))
    ids = iter(["dupdup12", "fresh123"])
    monkeypatch.setattr(service, "generate_id", lambda: next(ids))
    assert service.create_paste(db_session, "hi", "1h").id == "fresh123"


def test_get_paste_expired_returns_none(db_session):
    add_paste(db_session, "dead0001", expires_in=timedelta(seconds=-1))
    assert service.get_paste(db_session, "dead0001") is None
