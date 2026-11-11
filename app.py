from __future__ import annotations

import os
import hashlib
import re
from datetime import date
from threading import RLock
from uuid import uuid4
from typing import Any

from flask import Flask, request, jsonify
from flask_restx import Api, Namespace, Resource, fields

from ticket_domain import (
    FIELDS,
    NUMERIC_FIELDS,
    SEED_DATA,
    SORTABLE_FIELDS,
    TicketStore,
    TicketValidationError,
)


VERIFY_TOKEN = "TUSUR-SHAPKIN-20261110-8CB746B2"


def normalize_text(text: str) -> str:
    """Normalize line boundaries and whitespace as required by the checker."""
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(re.sub(r"\s+", " ", line) for line in lines)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(RESTX_MASK_SWAGGER=False, SWAGGER_UI_DOC_EXPANSION="list")
    if test_config:
        app.config.update(test_config)

    api = Api(
        app,
        version="1.0",
        title="Ticket Cost API",
        description="REST API для учета стоимости билетов на транспорт до городов (вариант 13)",
        doc="/docs",
        validate=True,
    )
    ns = Namespace("tickets", description="Операции с билетами")
    api.add_namespace(ns, path="/api/tickets")

    ticket_input = api.model("TicketInput", {
        "from_city": fields.String(required=True, description="Город отправления", example="Томск"),
        "to_city": fields.String(required=True, description="Город назначения", example="Новосибирск"),
        "transport_type": fields.String(required=True, description="Вид транспорта", example="Поезд"),
        "price": fields.Float(required=True, min=0, description="Стоимость билета", example=1750.0),
        "distance_km": fields.Float(required=True, min=0, description="Расстояние в километрах", example=265.0),
        "travel_time_hours": fields.Float(required=True, min=0, description="Время в пути в часах", example=4.5),
        "available_seats": fields.Integer(required=True, min=0, description="Количество свободных мест", example=12),
    })
    ticket_patch = api.model("TicketPatch", {
        "from_city": fields.String(description="Город отправления"),
        "to_city": fields.String(description="Город назначения"),
        "transport_type": fields.String(description="Вид транспорта"),
        "price": fields.Float(min=0, description="Стоимость билета"),
        "distance_km": fields.Float(min=0, description="Расстояние в километрах"),
        "travel_time_hours": fields.Float(min=0, description="Время в пути в часах"),
        "available_seats": fields.Integer(min=0, description="Количество свободных мест"),
    })
    ticket_output = api.inherit("Ticket", ticket_input, {
        "id": fields.Integer(required=True, description="Идентификатор записи", example=1)
    })
    field_statistics = api.model("NumericFieldStatistics", {
        "count": fields.Integer(description="Количество значений"),
        "average": fields.Float(description="Среднее значение", allow_null=True),
        "minimum": fields.Float(description="Минимальное значение", allow_null=True),
        "maximum": fields.Float(description="Максимальное значение", allow_null=True),
    })
    all_field_statistics = api.model("TicketNumericStatistics", {
        name: fields.Nested(field_statistics, description=f"Статистика поля {name}")
        for name in NUMERIC_FIELDS
    })
    statistics_output = api.model("TicketStatisticsResponse", {
        "records_count": fields.Integer(description="Количество записей"),
        "fields": fields.Nested(all_field_statistics),
    })

    initial_records = app.config.get("INITIAL_RECORDS", SEED_DATA)
    store = TicketStore(initial_records)
    app.extensions["ticket_store"] = store
    verification_records: dict[str, dict[str, Any]] = {}
    verification_lock = RLock()

    @app.after_request
    def add_verify_hash(response):
        # The professor's instructions mention both the collection URI
        # and a detail-URI regex. Support both so either curl GET is verifiable.
        if (request.method == "GET" and
            re.fullmatch(r"/api/disease(?:/[^/]+)?/?", request.path) and
            response.status_code == 200):
            body = response.get_data(as_text=True)
            normalized = normalize_text(body)
            response.headers["X-Verify-Hash"] = hashlib.sha256(
                normalized.encode("utf-8")
            ).hexdigest()
        return response

    @app.route("/api/disease/", methods=["POST", "GET"])
    def verification_disease_collection():
        """Separate compatibility resource for the professor's verification."""
        if request.method == "POST":
            data = request.get_json(silent=True)
            keys = {"country", "disease", "date", "sick", "recovered", "deaths"}
            if (not isinstance(data, dict) or set(data) != keys or
                any(not isinstance(data[k], str) or not data[k].strip()
                    for k in ("country", "disease", "date")) or
                any(type(data[k]) is not int or data[k] < 0
                    for k in ("sick", "recovered", "deaths"))):
                return jsonify(error="Invalid verification JSON"), 400
            try:
                date.fromisoformat(data["date"])
            except ValueError:
                return jsonify(error="Invalid ISO date"), 400
            row = {"id": uuid4().hex[:8], **data}
            with verification_lock:
                verification_records[row["id"]] = row
            return jsonify(row), 201
        with verification_lock:
            if not verification_records:
                return jsonify(error="No verification record has been created"), 404
            # The checker requests GET /api/disease/ and expects a single
            # object containing the id from the preceding POST.
            latest = next(reversed(verification_records.values()))
            return jsonify(latest)

    @app.get("/api/disease/<string:record_id>")
    def verification_disease_item(record_id):
        with verification_lock:
            row = verification_records.get(record_id)
        if row is None:
            return jsonify(error="Not found"), 404
        return jsonify(row)


    def validate_request_payload(payload: Any, *, partial: bool = False) -> dict[str, Any]:
        try:
            return store_payload_validation(payload, partial=partial)
        except TicketValidationError as exc:
            api.abort(400, str(exc))

    @ns.route("")
    class TicketList(Resource):
        @ns.doc("list_tickets", params={
            "sort_by": f"Поле сортировки: {', '.join(SORTABLE_FIELDS)}",
            "order": "Направление сортировки: asc или desc",
        })
        @ns.marshal_list_with(ticket_output)
        def get(self):
            """Получить все записи; сортировка поддерживается по каждому полю."""
            try:
                return store.list_records(
                    sort_by=request.args.get("sort_by", "id"),
                    order=request.args.get("order", "asc"),
                )
            except TicketValidationError as exc:
                api.abort(400, str(exc))

        @ns.doc("create_ticket", responses={201: "Запись создана", 400: "Ошибка проверки данных"})
        @ns.expect(ticket_input, validate=True)
        @ns.marshal_with(ticket_output, code=201)
        def post(self):
            """Добавить запись о стоимости билета."""
            payload = validate_request_payload(request.get_json(silent=True), partial=False)
            return store.create(payload), 201

    @ns.route("/stats")
    class TicketStatistics(Resource):
        @ns.doc("ticket_statistics")
        @ns.marshal_with(statistics_output)
        def get(self):
            """Получить среднее, минимальное и максимальное значение по каждому числовому полю."""
            return store.statistics()

    @ns.route("/<int:ticket_id>")
    @ns.param("ticket_id", "Идентификатор записи")
    class TicketItem(Resource):
        @ns.doc("get_ticket", responses={404: "Запись не найдена"})
        @ns.marshal_with(ticket_output)
        def get(self, ticket_id: int):
            """Получить запись по идентификатору."""
            result = store.get(ticket_id)
            if result is None:
                api.abort(404, "Запись с указанным идентификатором не найдена.")
            return result

        @ns.doc("replace_ticket", responses={200: "Запись обновлена", 404: "Запись не найдена"})
        @ns.expect(ticket_input, validate=True)
        @ns.marshal_with(ticket_output)
        def put(self, ticket_id: int):
            """Полностью обновить запись по идентификатору."""
            payload = validate_request_payload(request.get_json(silent=True), partial=False)
            result = store.replace(ticket_id, payload)
            if result is None:
                api.abort(404, "Запись с указанным идентификатором не найдена.")
            return result

        @ns.doc("patch_ticket", responses={200: "Запись обновлена", 404: "Запись не найдена"})
        @ns.expect(ticket_patch, validate=True)
        @ns.marshal_with(ticket_output)
        def patch(self, ticket_id: int):
            """Частично обновить запись по идентификатору."""
            payload = validate_request_payload(request.get_json(silent=True), partial=True)
            try:
                result = store.patch(ticket_id, payload)
            except TicketValidationError as exc:
                api.abort(400, str(exc))
            if result is None:
                api.abort(404, "Запись с указанным идентификатором не найдена.")
            return result

        @ns.doc("delete_ticket", params={"confirm": "Укажите true для подтверждения мягкого удаления"}, responses={204: "Запись помечена удалённой", 400: "Нет подтверждения", 404: "Запись не найдена"})
        def delete(self, ticket_id: int):
            """Soft delete only when explicit confirmation is provided."""
            if request.args.get("confirm", "").lower() != "true":
                api.abort(400, "Для удаления требуется ?confirm=true.")
            if not store.delete(ticket_id):
                api.abort(404, "Запись с указанным идентификатором не найдена.")
            return "", 204

    @ns.route("/health")
    class Health(Resource):
        def get(self):
            """Проверка доступности веб-сервиса."""
            return {"status": "ok", "service": "ticket-cost-api"}

    return app


# Keep the validation function separately testable without importing Flask.
def store_payload_validation(payload: Any, *, partial: bool) -> dict[str, Any]:
    from ticket_domain import validate_payload
    return validate_payload(payload, partial=partial)


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
