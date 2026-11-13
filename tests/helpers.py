"""Small helpers shared by tests."""

from datetime import UTC, datetime, timedelta

from app.models import Paste


def add_paste(session, paste_id: str, *, expires_in: timedelta, content: str = "x") -> Paste:
    """Insert a paste directly (bypassing the service) with a chosen expiry.

    A negative `expires_in` creates an already-expired paste, which is how tests
    simulate "time has passed" without sleeping.
    """
    now = datetime.now(UTC)
    paste = Paste(id=paste_id, content=content, created_at=now, expires_at=now + expires_in)
    session.add(paste)
    session.commit()
    return paste
