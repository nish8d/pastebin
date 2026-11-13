"""HTML pages: the form at "/" and the paste view at "/{paste_id}".

Same service layer as the JSON API, just a different way of presenting it:
HTML templates instead of JSON, a redirect instead of a 201.
"""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import service
from app.db import get_session

# Jinja2 autoescapes .html templates: "<script>" in a paste is shown as text, not run.
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")
router = APIRouter(tags=["web"])

PASTE_ID_RE = re.compile(r"[A-Za-z0-9]{8}")
DEFAULT_TTL = "1h"

# Which HTTP status to show for each kind of invalid input.
ERROR_STATUS = {
    service.EmptyContent: status.HTTP_400_BAD_REQUEST,
    service.InvalidTTL: status.HTTP_400_BAD_REQUEST,
    service.ContentTooLarge: status.HTTP_413_CONTENT_TOO_LARGE,
}


def render_form(request: Request, *, content: str = "", ttl: str = DEFAULT_TTL,
                error: str | None = None, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"ttl_labels": service.TTL_LABELS, "content": content,
         "selected_ttl": ttl if ttl in service.TTLS else DEFAULT_TTL, "error": error},
        status_code=status_code,
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return render_form(request)


@router.post("/")
def create_from_form(
    request: Request,
    content: str = Form(""),
    ttl: str = Form(DEFAULT_TTL),
    session: Session = Depends(get_session),
):
    try:
        paste = service.create_paste(session, content, ttl)
    except service.PasteError as e:
        # Re-show the form with the error and what the user typed, so nothing is lost.
        return render_form(request, content=content, ttl=ttl, error=str(e),
                           status_code=ERROR_STATUS[type(e)])
    # 303 See Other: "go GET this other page". Refreshing the result page then
    # won't re-submit the form (the Post/Redirect/Get pattern).
    return RedirectResponse(f"/{paste.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{paste_id}", response_class=HTMLResponse)
def show_paste(request: Request, paste_id: str, session: Session = Depends(get_session)):
    # Checked here rather than with Path(pattern=...) so a bad ID gets the friendly
    # 404 page instead of a 422 validation error.
    paste = service.get_paste(session, paste_id) if PASTE_ID_RE.fullmatch(paste_id) else None
    if paste is None:
        return templates.TemplateResponse(request, "not_found.html", {},
                                          status_code=status.HTTP_404_NOT_FOUND)
    return templates.TemplateResponse(request, "paste.html", {"paste": paste})
