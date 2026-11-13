"""Cleanup job: delete expired pastes. Run with `python -m app.cleanup`.

This is a short-lived script, not part of the web server. Something outside the
app starts it on a schedule:
  - systemd timer: deploy/systemd/pastebin-cleanup.timer (logs -> journalctl)
  - cron:          deploy/cron/pastebin-cleanup.cron      (logs -> logs/cleanup-cron.log)

Correctness doesn't depend on this job (reads already hide expired pastes);
it only reclaims storage. The exit code tells the scheduler whether it worked:
0 = success, 1 = failure (e.g. database down), which systemd records.
"""

import logging
import sys

from sqlalchemy.orm import Session

from app import repository
from app.db import SessionLocal

log = logging.getLogger("pastebin.cleanup")


def run_cleanup(session: Session) -> int:
    deleted = repository.delete_expired(session)
    log.info("cleanup: deleted %d expired paste(s)", deleted)
    return deleted


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        with SessionLocal() as session:
            run_cleanup(session)
    except Exception:
        log.exception("cleanup: failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
