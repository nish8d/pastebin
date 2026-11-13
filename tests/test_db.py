from datetime import UTC, datetime, timedelta

from app.models import Paste


def test_paste_roundtrip(db_session):
    now = datetime.now(UTC)
    db_session.add(
        Paste(id="abcd1234", content="hi", created_at=now, expires_at=now + timedelta(hours=1))
    )
    db_session.commit()
    db_session.expunge_all()

    paste = db_session.get(Paste, "abcd1234")
    assert paste.content == "hi"
    assert paste.expires_at.tzinfo is not None
