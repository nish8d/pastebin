"""Database tables, described as Python classes (SQLAlchemy ORM).

The real source of truth for the schema in production is the Alembic migration
in migrations/versions/. Keep the two in sync.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Paste(Base):
    __tablename__ = "pastes"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # timezone=True -> Postgres "timestamptz": stored as an absolute instant (UTC).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Indexed because both reads (expires_at > now()) and cleanup (expires_at <= now())
    # filter on it.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
