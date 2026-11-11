import hashlib
import re
import pytest

pytest.importorskip("flask")
pytest.importorskip("flask_restx")
from app import create_app, normalize_text, VERIFY_TOKEN

@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()

def test_confirmation_and_soft_delete(client):
    res = client.post("/api/tickets", json={
        "from_city": "Томск", "to_city": "Омск", "transport_type": "Поезд",
        "price": 2000, "distance_km": 900, "travel_time_hours": 12, "available_seats": 10,
    })
    assert res.status_code == 201
    idx = res.get_json()["id"]
    assert client.delete(f"/api/tickets/{idx}").status_code == 400
    assert client.get(f"/api/tickets/{idx}").status_code == 200
    assert client.delete(f"/api/tickets/{idx}?confirm=true").status_code == 204
    assert client.get(f"/api/tickets/{idx}").status_code == 404
    assert all(item["id"] != idx for item in client.get("/api/tickets").get_json())
    from_store = client.application.extensions["ticket_store"]
    assert from_store.get_deleted(idx)["is_deleted"] is True

def test_verification_post_and_get_hash(client):
    payload = {"country": "Verification", "disease": VERIFY_TOKEN,
               "date": "2026-11-08", "sick": 0, "recovered": 0, "deaths": 0}
    created = client.post("/api/disease/", json=payload)
    assert created.status_code == 201
    idx = created.get_json()["id"]
    for uri in ("/api/disease/", f"/api/disease/{idx}"):
        res = client.get(uri)
        assert res.status_code == 200
        assert len(res.headers["X-Verify-Hash"]) == 64
        expected = hashlib.sha256(normalize_text(res.get_data(as_text=True)).encode()).hexdigest()
        assert res.headers["X-Verify-Hash"] == expected
    assert client.get("/api/disease/").get_json()["disease"] == VERIFY_TOKEN
    assert client.get("/api/disease/").get_json()["id"] == idx

def test_verify_validation(client):
    assert client.post("/api/disease/", json={"country": "x"}).status_code == 400
    assert client.get("/api/disease/missing").status_code == 404
