import logging
from datetime import timedelta

from app import cleanup
from app.models import Paste
from tests.helpers import add_paste


def test_run_cleanup_deletes_and_logs(db_session, caplog):
    add_paste(db_session, "dead0001", expires_in=timedelta(seconds=-1))
    add_paste(db_session, "live0001", expires_in=timedelta(hours=1))

    with caplog.at_level(logging.INFO):
        assert cleanup.run_cleanup(db_session) == 1
    assert "cleanup: deleted 1 expired paste(s)" in caplog.text
    assert db_session.get(Paste, "live0001") is not None

    assert cleanup.run_cleanup(db_session) == 0
