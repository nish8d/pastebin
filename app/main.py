"""Application entry point: builds the FastAPI app and wires the pieces together.

Run locally with:  uv run uvicorn app.main:app --port 8000
In deployment, systemd runs the same command (deploy/systemd/pastebin-app.service).
"""

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import api, web

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Pastebin")

    @app.get("/healthz", tags=["ops"])
    def healthz(session: Session = Depends(get_session)):
        """Liveness + DB check. Handy for `curl` during deployment and for monitoring."""
        try:
            session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "db_unavailable"}, status_code=503)
        return {"status": "ok"}

    # Order matters: specific routes (/api/..., /healthz, /static) are registered
    # before the web router's catch-all "/{paste_id}".
    app.include_router(api.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(web.router)
    return app


app = create_app()
