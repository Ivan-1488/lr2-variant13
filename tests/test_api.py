import pytest

pytest.importorskip("flask")
pytest.importorskip("flask_restx")

from app import create_app
from ticket_domain import SORTABLE_FIELDS


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def sample():
    return {
        "from_city": "Томск", "to_city": "Омск", "transport_type": "Поезд",
        "price": 2100, "distance_km": 900, "travel_time_hours": 12.5, "available_seats": 17,
    }


def test_list_returns_seed_data(client):
    response = client.get("/api/tickets")
    assert response.status_code == 200
    assert len(response.get_json()) >= 5


@pytest.mark.parametrize("field", SORTABLE_FIELDS)
def test_sort_by_every_supported_field(client, field):
    response = client.get(f"/api/tickets?sort_by={field}&order=asc")
    assert response.status_code == 200
    records = response.get_json()
    values = [row[field].casefold() if isinstance(row[field], str) else row[field] for row in records]
    assert values == sorted(values)


def test_sort_descending_by_numeric_field(client):
    response = client.get("/api/tickets?sort_by=price&order=desc")
    assert response.status_code == 200
    prices = [item["price"] for item in response.get_json()]
    assert prices == sorted(prices, reverse=True)


def test_reject_invalid_sort_field(client):
    assert client.get("/api/tickets?sort_by=unknown").status_code == 400


def test_statistics_cover_every_numeric_field(client):
    response = client.get("/api/tickets/stats")
    assert response.status_code == 200
    fields = response.get_json()["fields"]
    assert set(fields) == {"price", "distance_km", "travel_time_hours", "available_seats"}
    assert all({"average", "minimum", "maximum", "count"} <= set(stats) for stats in fields.values())


def test_crud_lifecycle(client):
    created = client.post("/api/tickets", json=sample())
    assert created.status_code == 201
    item_id = created.get_json()["id"]
    assert isinstance(item_id, int)
    assert created.get_json()["to_city"] == "Омск"
    assert client.get(f"/api/tickets/{item_id}").status_code == 200

    updated = client.patch(f"/api/tickets/{item_id}", json={"price": 2400})
    assert updated.status_code == 200
    assert updated.get_json()["price"] == 2400

    replacement = sample()
    replacement["price"] = 2500
    assert client.put(f"/api/tickets/{item_id}", json=replacement).status_code == 200
    assert client.delete(f"/api/tickets/{item_id}").status_code == 400
    assert client.delete(f"/api/tickets/{item_id}?confirm=true").status_code == 204
    assert client.get(f"/api/tickets/{item_id}").status_code == 404


def test_create_rejects_negative_price(client):
    payload = sample()
    payload["price"] = -10
    assert client.post("/api/tickets", json=payload).status_code == 400


def test_create_requires_all_domain_fields(client):
    payload = sample()
    del payload["distance_km"]
    assert client.post("/api/tickets", json=payload).status_code == 400


def test_swagger_ui_is_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert b"swagger" in response.data.lower()


def test_health_endpoint(client):
    response = client.get("/api/tickets/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
