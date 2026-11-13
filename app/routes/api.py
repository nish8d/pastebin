"""JSON API: /api/pastes.

Routes are thin: parse the request, call the service, turn the result (or a
service error) into an HTTP response. All the rules live in service.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import service
from app.config import get_settings
from app.db import get_session
from app.schemas import PasteCreate, PasteCreated, PasteOut

router = APIRouter(prefix="/api/pastes", tags=["api"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PasteCreated)
def create_paste(body: PasteCreate, session: Session = Depends(get_session)) -> PasteCreated:
    try:
        paste = service.create_paste(session, body.content, body.ttl)
    except service.EmptyContent as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except service.ContentTooLarge as e:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(e))
    except service.InvalidTTL as e:  # normally caught earlier by the schema's Literal
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    return PasteCreated(
        id=paste.id, url=f"{get_settings().base_url}/{paste.id}", expires_at=paste.expires_at
    )


@router.get("/{paste_id}", response_model=PasteOut)
def get_paste(paste_id: str, session: Session = Depends(get_session)) -> PasteOut:
    paste = service.get_paste(session, paste_id)
    if paste is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paste not found or expired.")
    return PasteOut.model_validate(paste, from_attributes=True)
