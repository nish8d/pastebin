import re
from datetime import timedelta

from tests.helpers import add_paste


def test_index_has_form_and_ttls(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="content"' in r.text and 'name="ttl"' in r.text
    for label in ["1 minute", "10 minutes", "1 hour", "1 day", "1 week"]:
        assert label in r.text
    assert re.search(r'<option value="1h"\s+selected', r.text)


def test_form_post_redirects(client):
    r = client.post("/", data={"content": "from the form", "ttl": "1h"}, follow_redirects=False)
    assert r.status_code == 303
    assert re.fullmatch(r"/[A-Za-z0-9]{8}", r.headers["location"])


def test_paste_page_shows_content(client):
    r = client.post("/", data={"content": "line one\nline two", "ttl": "1h"})
    assert r.status_code == 200
    assert "line one\nline two" in r.text
    assert "Expires" in r.text and "Copy link" in r.text


def test_script_is_escaped(client):
    r = client.post("/", data={"content": "<script>alert(1)</script>", "ttl": "1h"})
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.text
    assert "<script>alert" not in r.text


def test_form_bad_ttl_400(client):
    r = client.post("/", data={"content": "hi", "ttl": "99y"})
    assert r.status_code == 400
    assert "Unknown expiry option" in r.text


def test_form_empty_400_keeps_form(client):
    r = client.post("/", data={"content": "   ", "ttl": "1h"})
    assert r.status_code == 400
    assert "Paste content is empty." in r.text
    assert 'name="content"' in r.text


def test_form_error_keeps_typed_text(client):
    r = client.post("/", data={"content": "keep me", "ttl": "99y"})
    assert "keep me" in r.text


def test_form_is_multipart(client):
    # URL-encoding turns "é" into "%C3%A9" (6 bytes), so a 512 KiB paste could exceed
    # Starlette's 1 MB form-field limit. Multipart sends the text as-is.
    assert 'enctype="multipart/form-data"' in client.get("/").text


def multipart(**fields):
    """Encode fields the way the browser sends our form (multipart/form-data)."""
    return {name: (None, value) for name, value in fields.items()}


def test_form_too_large_413(client):
    r = client.post("/", files=multipart(content="é" * 262145, ttl="1h"))
    assert r.status_code == 413
    assert "larger than 512 KiB" in r.text


def test_form_multibyte_under_limit_ok(client):
    r = client.post("/", files=multipart(content="é" * 262144, ttl="1h"), follow_redirects=False)
    assert r.status_code == 303


def test_expired_page_404(client, db_session):
    add_paste(db_session, "dead0001", expires_in=timedelta(seconds=-1))
    r = client.get("/dead0001")
    assert r.status_code == 404
    assert "not found or expired" in r.text.lower()


def test_reserved_paths_not_ids(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/favicon.ico").status_code == 404
    assert client.get("/abc").status_code == 404
