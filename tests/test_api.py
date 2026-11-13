from datetime import timedelta

from tests.helpers import add_paste


def test_create_and_get(client):
    r = client.post("/api/pastes", json={"content": "hello api", "ttl": "10m"})
    assert r.status_code == 201
    body = r.json()
    assert body["url"].endswith("/" + body["id"])
    assert body["url"].startswith("http://localhost:8080/")

    r = client.get(f"/api/pastes/{body['id']}")
    assert r.status_code == 200
    assert r.json()["content"] == "hello api"
    assert r.json()["expires_at"] == body["expires_at"]


def test_unknown_ttl_422(client):
    r = client.post("/api/pastes", json={"content": "hi", "ttl": "99y"})
    assert r.status_code == 422


def test_empty_422(client):
    r = client.post("/api/pastes", json={"content": "  \n", "ttl": "1h"})
    assert r.status_code == 422
    assert r.json() == {"detail": "Paste content is empty."}


def test_too_large_413(client):
    r = client.post("/api/pastes", json={"content": "é" * 262145, "ttl": "1h"})
    assert r.status_code == 413
    assert r.json() == {"detail": "Paste is larger than 512 KiB."}


def test_get_missing_404(client):
    r = client.get("/api/pastes/nothere1")
    assert r.status_code == 404
    assert r.json() == {"detail": "Paste not found or expired."}


def test_get_expired_404(client, db_session):
    add_paste(db_session, "dead0001", expires_in=timedelta(seconds=-1))
    assert client.get("/api/pastes/dead0001").status_code == 404


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_schema_ttls_match_service():
    from typing import get_args

    from app import service
    from app.schemas import TTLChoice

    assert list(get_args(TTLChoice)) == list(service.TTLS)
