# Лабораторная работа № 2. Вариант 13

## Предметная область

Стоимость билетов на транспорт до городов.

## Модель данных

У каждой записи есть служебное целочисленное поле `id` и семь предметных полей:

| Поле | Тип | Назначение |
|---|---|---|
| `from_city` | string | Город отправления |
| `to_city` | string | Город назначения |
| `transport_type` | string | Вид транспорта |
| `price` | float | Стоимость билета |
| `distance_km` | float | Расстояние в километрах |
| `travel_time_hours` | float | Время в пути в часах |
| `available_seats` | integer | Количество свободных мест |

Таким образом, в модели три строковых и четыре числовых предметных поля (не считая идентификатора), что выполняет требование методических указаний. Хранение реализовано в памяти процесса без СУБД, поскольку пособие не требует обязательного использования базы данных. После перезапуска приложения изменения сбрасываются к демонстрационному набору.

## Реализовано

- Flask REST API с интерактивной Swagger-документацией Flask-RESTX (`/docs`). В проекте используется совместимый преемник Flask-RESTPlus из примеров пособия; сохраняется подход с моделями данных, ресурсами, сериализацией и Swagger UI, но применяются актуальные зависимости.
- Получение полного набора записей и отдельной записи по `id`.
- Сортировка по `id` и каждому предметному полю: `sort_by` и `order=asc|desc`.
- Статистика по каждому числовому полю: количество значений, среднее, минимум и максимум.
- Добавление (`POST`), полное обновление (`PUT`), частичное обновление (`PATCH`) и удаление (`DELETE`).
- Валидация типов, обязательных полей, непустых строк и запрет отрицательных числовых значений.
- Демонстрационный набор начальных записей.
- Автоматические тесты API на pytest.

## Структура проекта

```text
LR2_variant13/
├── .github/workflows/tests.yml
├── app.py
├── ticket_domain.py
├── requirements.txt
├── render.yaml
├── tests/test_api.py
├── tests/test_domain.py
├── examples/generate_demo_data.py
└── README.md
```

## Локальный запуск (Python 3.11)

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Базовый адрес: `http://127.0.0.1:5000`. Swagger UI: `http://127.0.0.1:5000/docs`.

## API

| Метод | URL | Назначение |
|---|---|---|
| GET | `/api/tickets` | Все записи; поддерживает `?sort_by=price&order=desc` |
| GET | `/api/tickets/{id}` | Одна запись |
| GET | `/api/tickets/stats` | Статистика числовых полей |
| POST | `/api/tickets` | Добавить запись |
| PUT | `/api/tickets/{id}` | Полностью заменить запись |
| PATCH | `/api/tickets/{id}` | Изменить переданные поля |
| DELETE | `/api/tickets/{id}` | Удалить запись |
| GET | `/api/tickets/health` | Проверка доступности сервиса |

### Пример тела POST/PUT

```json
{
  "from_city": "Томск",
  "to_city": "Омск",
  "transport_type": "Поезд",
  "price": 2100.0,
  "distance_km": 900.0,
  "travel_time_hours": 12.5,
  "available_seats": 17
}
```

### Примеры запросов

```bash
curl "http://127.0.0.1:5000/api/tickets?sort_by=price&order=desc"
curl "http://127.0.0.1:5000/api/tickets/stats"
curl -X POST "http://127.0.0.1:5000/api/tickets" -H "Content-Type: application/json" -d '{"from_city":"Томск","to_city":"Омск","transport_type":"Поезд","price":2100,"distance_km":900,"travel_time_hours":12.5,"available_seats":17}'
curl -X PATCH "http://127.0.0.1:5000/api/tickets/1" -H "Content-Type: application/json" -d '{"price":2200}'
curl -X DELETE "http://127.0.0.1:5000/api/tickets/1"
```

## Контрольный пример и проверка тестами

Для формирования детерминированных примеров ответов из демонстрационного набора выполните:

```bash
python examples/generate_demo_data.py
```

Скрипт создаст `examples/demo_api_responses.json` с результатами получения записей, сортировки по цене и статистики. Это данные демонстрационной модели, а не реальные тарифы.

Полный набор тестов (включая HTTP-обработчики Flask-RESTX) запускается после установки зависимостей:

```bash
pytest -q
```

## Результат локальной проверки в подготовительной среде

- `tests/test_domain.py`: **13 passed**. Проверены модель данных, типы и валидация, сортировка, статистика и CRUD-цикл хранилища.
- HTTP-модуль `tests/test_api.py`: **skipped**, поскольку в среде проверки не были установлены Flask и Flask-RESTX. Маршруты API и Swagger UI нужно проверить после установки зависимостей.

## CI и размещение

GitHub Actions выполняет `pytest` при push и pull request. Для Render в корне проекта предусмотрен `render.yaml`; команда запуска: `gunicorn app:app --bind 0.0.0.0:$PORT`.

Для данной учебной реализации хранение выполняется в оперативной памяти. Для демонстрационного запуска Render следует оставить один worker Gunicorn, иначе у каждого worker будет собственная копия списка записей. В `render.yaml` команда запуска использует значение Gunicorn по умолчанию, то есть один worker.

## Переменные окружения

| Переменная | Назначение | Обязательность |
|---|---|---|
| `PORT` | Порт веб-сервера | Необязательная, по умолчанию `5000` |


## Исправления по повторной проверке

- Основной API вариантов 13 сохранён: `/api/tickets`. DELETE по `/api/tickets/<id>?confirm=true` требует явного подтверждения, помечает запись `is_deleted=True` и исключает из списка, статистики и обычного GET. Без `confirm=true` возвращается 400. Данные остаются только в оперативной памяти и теряются при перезапуске.
- По отдельному требованию проверки добавлен совместимый ресурс `/api/disease/` (POST, GET) и `/api/disease/<id>` (GET). Запись создаётся из JSON преподавателя. GET содержит заголовок `X-Verify-Hash`, рассчитанный по нормализованному UTF-8 JSON-телу.
- В задании преподавателя есть противоречие: curl GET запрашивает `/api/disease/`, а пример `after_request` сопоставляет только `/api/disease/<id>`. Реализовано хэширование обоих вариантов.
- `VERIFY_TOKEN` расположен в `app.py`.
- Выполнить `python -m pytest -q` после установки зависимостей. Реальный хостинг и curl должны проверяться отдельно; выводы с внешнего адреса здесь не создавались.
