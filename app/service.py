"""Business rules for pastes.

This layer decides *what is allowed*: which lifetimes exist, how big a paste may
be, how IDs are made. It doesn't know about HTTP (routes translate its errors
into status codes) or SQL (repository.py does that).
"""

import secrets
import string
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import repository
from app.models import Paste

# Allowed lifetimes. The keys are what clients send ("ttl": "1h").
TTLS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "10m": timedelta(minutes=10),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(days=7),
}
TTL_LABELS: dict[str, str] = {
    "1m": "1 minute",
    "10m": "10 minutes",
    "1h": "1 hour",
    "1d": "1 day",
    "1w": "1 week",
}

MAX_CONTENT_BYTES = 512 * 1024  # 524288 bytes, measured as UTF-8
ID_LENGTH = 8
ID_ALPHABET = string.ascii_letters + string.digits  # 62 symbols -> 62**8 ≈ 2.2e14 IDs
MAX_ID_ATTEMPTS = 5


class PasteError(Exception):
    """Base class for 'the request was invalid' errors."""


class EmptyContent(PasteError):
    pass


class ContentTooLarge(PasteError):
    pass


class InvalidTTL(PasteError):
    pass


def generate_id() -> str:
    """Random, unguessable short ID. `secrets` (not `random`) is cryptographically
    secure, so people can't enumerate other users' pastes."""
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(ID_LENGTH))


def create_paste(session: Session, content: str, ttl: str) -> Paste:
    """Validate input, store the paste, and return it."""
    if not content.strip():
        raise EmptyContent("Paste content is empty.")
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise ContentTooLarge("Paste is larger than 512 KiB.")
    if ttl not in TTLS:
        raise InvalidTTL(f"Unknown expiry option: {ttl!r}.")

    created_at = datetime.now(UTC)
    expires_at = created_at + TTLS[ttl]

    # Collisions are astronomically rare, but the primary key would reject one,
    # so retry with a fresh ID instead of failing the user's request.
    for attempt in range(MAX_ID_ATTEMPTS):
        try:
            paste = repository.insert_paste(
                session,
                paste_id=generate_id(),
                content=content,
                created_at=created_at,
                expires_at=expires_at,
            )
            session.commit()
            return paste
        except IntegrityError:
            session.rollback()
            if attempt == MAX_ID_ATTEMPTS - 1:
                raise
    raise AssertionError("unreachable")


def get_paste(session: Session, paste_id: str) -> Paste | None:
    """Return a live (unexpired) paste, or None."""
    return repository.get_live_paste(session, paste_id)
