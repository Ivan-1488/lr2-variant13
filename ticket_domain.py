"""Domain model and in-memory storage for Laboratory Work 2, variant 13."""
from __future__ import annotations

import math
from copy import deepcopy
from threading import RLock
from typing import Any

FIELDS: dict[str, type] = {
    "from_city": str,
    "to_city": str,
    "transport_type": str,
    "price": float,
    "distance_km": float,
    "travel_time_hours": float,
    "available_seats": int,
}
STRING_FIELDS = ("from_city", "to_city", "transport_type")
NUMERIC_FIELDS = ("price", "distance_km", "travel_time_hours", "available_seats")
SORTABLE_FIELDS = ("id",) + tuple(FIELDS)

SEED_DATA: list[dict[str, Any]] = [
    {"id": 1, "from_city": "Томск", "to_city": "Новосибирск", "transport_type": "Автобус", "price": 1250.0, "distance_km": 265.0, "travel_time_hours": 4.5, "available_seats": 12},
    {"id": 2, "from_city": "Томск", "to_city": "Москва", "transport_type": "Самолёт", "price": 8900.0, "distance_km": 2880.0, "travel_time_hours": 4.2, "available_seats": 8},
    {"id": 3, "from_city": "Москва", "to_city": "Санкт-Петербург", "transport_type": "Поезд", "price": 3200.0, "distance_km": 700.0, "travel_time_hours": 8.0, "available_seats": 24},
    {"id": 4, "from_city": "Казань", "to_city": "Самара", "transport_type": "Автобус", "price": 980.0, "distance_km": 360.0, "travel_time_hours": 5.0, "available_seats": 5},
    {"id": 5, "from_city": "Екатеринбург", "to_city": "Пермь", "transport_type": "Поезд", "price": 1450.0, "distance_km": 360.0, "travel_time_hours": 6.3, "available_seats": 16},
]


class TicketValidationError(ValueError):
    """Raised when a request does not match the ticket data model."""


class TicketStore:
    """Thread-safe in-memory repository used by the educational REST API."""

    def __init__(self, initial_records: list[dict[str, Any]] | None = None):
        self._records = deepcopy(SEED_DATA if initial_records is None else initial_records)
        self._next_id = max((int(row["id"]) for row in self._records), default=0) + 1
        self._lock = RLock()

    def list_records(self, sort_by: str = "id", order: str = "asc") -> list[dict[str, Any]]:
        if sort_by not in SORTABLE_FIELDS:
            raise TicketValidationError(
                f"Недопустимое поле сортировки. Допустимые поля: {', '.join(SORTABLE_FIELDS)}"
            )
        order = order.lower()
        if order not in {"asc", "desc"}:
            raise TicketValidationError("Параметр order должен быть asc или desc.")
        with self._lock:
            result = deepcopy([r for r in self._records if not r.get("is_deleted", False)])
        result.sort(
            key=lambda row: row[sort_by].casefold() if isinstance(row[sort_by], str) else row[sort_by],
            reverse=(order == "desc"),
        )
        return result

    def get(self, ticket_id: int) -> dict[str, Any] | None:
        with self._lock:
            for row in self._records:
                if row["id"] == ticket_id and not row.get("is_deleted", False):
                    return deepcopy(row)
        return None

    def create(self, payload: Any) -> dict[str, Any]:
        valid = validate_payload(payload, partial=False)
        with self._lock:
            row = {"id": self._next_id, **valid, "is_deleted": False}
            self._next_id += 1
            self._records.append(row)
            return deepcopy(row)

    def replace(self, ticket_id: int, payload: Any) -> dict[str, Any] | None:
        valid = validate_payload(payload, partial=False)
        with self._lock:
            for index, row in enumerate(self._records):
                if row["id"] == ticket_id and not row.get("is_deleted", False):
                    self._records[index] = {"id": ticket_id, **valid, "is_deleted": False}
                    return deepcopy(self._records[index])
        return None

    def patch(self, ticket_id: int, payload: Any) -> dict[str, Any] | None:
        valid = validate_payload(payload, partial=True)
        if not valid:
            raise TicketValidationError("Передайте хотя бы одно поле для обновления.")
        with self._lock:
            for row in self._records:
                if row["id"] == ticket_id and not row.get("is_deleted", False):
                    row.update(valid)
                    return deepcopy(row)
        return None

    def delete(self, ticket_id: int) -> bool:
        """Soft delete: preserve the record, hide it from normal operations."""
        with self._lock:
            for row in self._records:
                if row["id"] == ticket_id and not row.get("is_deleted", False):
                    row["is_deleted"] = True
                    return True
        return False

    def get_deleted(self, ticket_id: int) -> dict[str, Any] | None:
        """Read archived records for administrative verification only."""
        with self._lock:
            for row in self._records:
                if row["id"] == ticket_id and row.get("is_deleted", False):
                    return deepcopy(row)
        return None

    def statistics(self) -> dict[str, Any]:
        records = self.list_records()
        result: dict[str, Any] = {"records_count": len(records), "fields": {}}
        for field in NUMERIC_FIELDS:
            values = [float(row[field]) for row in records]
            result["fields"][field] = {
                "count": len(values),
                "average": round(sum(values) / len(values), 2) if values else None,
                "minimum": min(values) if values else None,
                "maximum": max(values) if values else None,
            }
        return result


def validate_payload(payload: Any, *, partial: bool) -> dict[str, Any]:
    """Validate and normalize a complete or partial ticket JSON object."""
    if not isinstance(payload, dict):
        raise TicketValidationError("Тело запроса должно быть JSON-объектом.")
    allowed = set(FIELDS)
    unknown = set(payload) - allowed
    if unknown:
        raise TicketValidationError(f"Неизвестные поля: {', '.join(sorted(unknown))}.")
    if not partial:
        missing = allowed - set(payload)
        if missing:
            raise TicketValidationError(f"Не заполнены обязательные поля: {', '.join(sorted(missing))}.")

    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key in STRING_FIELDS:
            if not isinstance(value, str) or not value.strip():
                raise TicketValidationError(f"Поле {key} должно содержать непустую строку.")
            result[key] = value.strip()
        elif key == "available_seats":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise TicketValidationError("Поле available_seats должно быть целым неотрицательным числом.")
            result[key] = value
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TicketValidationError(f"Поле {key} должно быть числом.")
            number = float(value)
            if not math.isfinite(number):
                raise TicketValidationError(f"Поле {key} должно быть конечным числом.")
            if number < 0:
                raise TicketValidationError(f"Поле {key} не может быть отрицательным.")
            result[key] = number
    return result
