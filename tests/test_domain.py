import pytest

from ticket_domain import (
    NUMERIC_FIELDS,
    SEED_DATA,
    TicketStore,
    TicketValidationError,
    validate_payload,
)


def sample():
    return {
        "from_city": "Томск", "to_city": "Омск", "transport_type": "Поезд",
        "price": 2100, "distance_km": 900, "travel_time_hours": 12.5, "available_seats": 17,
    }


def test_seed_records_match_domain_model():
    assert len(SEED_DATA) >= 5
    assert all(set(row) == {"id", "from_city", "to_city", "transport_type", *NUMERIC_FIELDS} for row in SEED_DATA)


def test_validate_normalizes_strings_and_numeric_values():
    payload = sample()
    payload["from_city"] = "  Томск  "
    result = validate_payload(payload, partial=False)
    assert result["from_city"] == "Томск"
    assert result["price"] == 2100.0
    assert result["available_seats"] == 17


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_validate_rejects_invalid_numeric_price(value):
    payload = sample()
    payload["price"] = value
    with pytest.raises(TicketValidationError):
        validate_payload(payload, partial=False)


def test_validate_rejects_fractional_seat_count():
    payload = sample()
    payload["available_seats"] = 2.5
    with pytest.raises(TicketValidationError):
        validate_payload(payload, partial=False)


def test_validate_requires_all_fields_on_create():
    payload = sample()
    del payload["distance_km"]
    with pytest.raises(TicketValidationError):
        validate_payload(payload, partial=False)


def test_sorting_works_for_each_data_type_and_direction():
    store = TicketStore()
    assert store.list_records("price", "desc")[0]["price"] == 8900.0
    assert store.list_records("from_city", "asc")[0]["from_city"] == "Екатеринбург"
    assert store.list_records("available_seats", "asc")[0]["available_seats"] == 5


def test_invalid_sort_parameters_are_rejected():
    store = TicketStore()
    with pytest.raises(TicketValidationError):
        store.list_records("wrong")
    with pytest.raises(TicketValidationError):
        store.list_records("price", "up")


def test_statistics_cover_all_numeric_fields():
    store = TicketStore()
    result = store.statistics()
    assert set(result["fields"]) == set(NUMERIC_FIELDS)
    assert result["records_count"] == 5
    assert result["fields"]["price"]["minimum"] == 980.0
    assert result["fields"]["price"]["maximum"] == 8900.0


def test_empty_store_statistics_are_defined():
    result = TicketStore([]).statistics()
    assert result["records_count"] == 0
    assert all(values["count"] == 0 and values["average"] is None for values in result["fields"].values())


def test_crud_lifecycle_and_identifier_generation():
    store = TicketStore([])
    created = store.create(sample())
    assert created["id"] == 1
    assert store.get(1)["to_city"] == "Омск"
    patched = store.patch(1, {"price": 2400})
    assert patched["price"] == 2400.0
    replaced = store.replace(1, {**sample(), "price": 2500})
    assert replaced["price"] == 2500.0
    assert store.delete(1) is True
    assert store.get_deleted(1)["is_deleted"] is True
    assert store.get(1) is None
    assert store.delete(1) is False
