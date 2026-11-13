"""Data access layer: the only module that knows how pastes are stored.

Functions here speak SQL (via SQLAlchemy) and nothing else: no HTTP, no
validation, no business rules. That keeps them small and easy to test, and means
swapping the storage later only touches this file.
"""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Paste


def insert_paste(
    session: Session, *, paste_id: str, content: str, created_at: datetime, expires_at: datetime
) -> Paste:
    """Add a paste and flush it to the database (without committing).

    Flushing sends the INSERT now, so a duplicate id raises IntegrityError here
    rather than later at commit time. The caller decides when to commit.
    """
    paste = Paste(id=paste_id, content=content, created_at=created_at, expires_at=expires_at)
    session.add(paste)
    session.flush()
    return paste


def get_live_paste(session: Session, paste_id: str) -> Paste | None:
    """Return the paste only if it has not expired yet.

    This filter is expiry layer 1 (correctness): an expired row is never served,
    even if the cleanup job hasn't deleted it yet. `func.now()` is the database
    clock, the same clock the cleanup job uses.
    """
    stmt = select(Paste).where(Paste.id == paste_id, Paste.expires_at > func.now())
    return session.scalars(stmt).first()


def delete_expired(session: Session) -> int:
    """Delete every expired paste and return how many were removed.

    This is expiry layer 2 (storage hygiene), called by the scheduled cleanup job.
    Safe to run any number of times, even concurrently: a second run simply finds
    nothing left to delete.
    """
    result = session.execute(delete(Paste).where(Paste.expires_at <= func.now()))
    session.commit()
    return result.rowcount
