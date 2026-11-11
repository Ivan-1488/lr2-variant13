"""Generate deterministic API examples from the same domain model as the service."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ticket_domain import TicketStore

store = TicketStore()
result = {
    "GET /api/tickets": store.list_records(),
    "GET /api/tickets?sort_by=price&order=desc": store.list_records("price", "desc"),
    "GET /api/tickets/stats": store.statistics(),
}
out = Path(__file__).with_name("demo_api_responses.json")
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved: {out}")
