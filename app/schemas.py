"""Shapes of JSON requests and responses for the API (validated by Pydantic)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Kept in sync with service.TTLS; a test checks the keys match.
TTLChoice = Literal["1m", "10m", "1h", "1d", "1w"]


class PasteCreate(BaseModel):
    content: str
    ttl: TTLChoice


class PasteCreated(BaseModel):
    id: str
    url: str
    expires_at: datetime


class PasteOut(BaseModel):
    id: str
    content: str
    created_at: datetime
    expires_at: datetime
