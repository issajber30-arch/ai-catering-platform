# API Contracts (preliminary)

Status: **Draft v0.1**. `/health`, the catalog, availability, public-config and the Admin catalog/logistics routes are implemented (Phases 1-2); orders and AI are not. Everything else is a design target and may change.

Base: same origin as the frontend. JSON only. All bodies validated with Pydantic.

## Error format

```json
{ "error": { "code": "order_version_conflict", "message": "Human readable", "details": {} } }
```

Common codes: `conflict` (409), `file_too_large` (413), `unsupported_media_type` (415), `validation_error` (422), `not_found` (404), `forbidden` (403), `unauthenticated` (401), `invalid_transition` (409), `order_version_conflict` (409), `proposal_not_pending` (409).

## System

| Method | Path | Response | Phase |
|---|---|---|---|
| GET | `/health` | `{"status":"ok","env":"development"}` | **1 (implemented)** |

## Catalog (public read)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/catalog/categories` | Active categories, ordered |
| GET | `/api/catalog/dishes?category_id=&vegan=&vegetarian=&kashrut=` | Available dishes with price, unit, dietary info (unknown fields returned as `null`) |
| GET | `/api/catalog/dishes/{id}` | Dish detail incl. allergen statuses |
| GET | `/api/availability?from=&to=` | Blocked dates + slots |

## Customer orders (auth model **[OPEN #1]**)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders` | Create draft from event config |
| GET | `/api/orders/{id}` | Order with items, live pricing, `version` |
| PATCH | `/api/orders/{id}` | Update event/fulfillment details; requires `version` |
| PUT | `/api/orders/{id}/items/{dish_id}` | Set quantity; requires `version` |
| DELETE | `/api/orders/{id}/items/{dish_id}` | Remove dish; requires `version` |
| GET | `/api/orders/{id}/pricing` | Itemized breakdown |
| GET | `/api/orders/{id}/recommendations` | Quantity recommendations (rules **[OPEN #3]**) |
| POST | `/api/orders/{id}/submit` | `draft → pending_approval`; freezes snapshot |

Every mutation returns the full updated order (new `version`). A stale `version` → `409 order_version_conflict`.

## AI assistant (Phase 4)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders/{id}/chat` | `{message}` → `{reply, proposals:[...]}` |
| GET | `/api/orders/{id}/proposals?status=pending` | |
| POST | `/api/orders/{id}/proposals/{pid}/approve` | Executes in one transaction if `base_order_version == order.version` and status `pending` |
| POST | `/api/orders/{id}/proposals/{pid}/reject` | No mutation |

Proposal shape:

```json
{
  "id": "uuid",
  "base_order_version": 7,
  "changes": [
    {"op": "add_item", "dish_id": "uuid", "quantity": 2},
    {"op": "set_quantity", "dish_id": "uuid", "quantity": 4},
    {"op": "remove_item", "dish_id": "uuid"},
    {"op": "update_details", "fields": {"requested_at": "..."}}
  ],
  "diff": [{"label": "...", "current": "...", "proposed": "..."}],
  "price_before": "1200.00",
  "price_after": "1350.00",
  "status": "pending"
}
```

## Admin (owner only)

| Method | Path |
|---|---|
| GET/POST | `/api/admin/categories` · PATCH/DELETE `/api/admin/categories/{id}` |
| GET/POST | `/api/admin/dishes` · PATCH/DELETE `/api/admin/dishes/{id}` |
| GET | `/api/admin/allergens` (read-only list, Phase 2) |
| POST | `/api/admin/dishes/{id}/image` (multipart → Supabase Storage) |
| PUT | `/api/admin/dishes/{id}/dietary` |
| GET/POST/PATCH/DELETE | `/api/admin/delivery-zones` |
| GET/POST/PATCH/DELETE | `/api/admin/time-slots` |
| GET/POST/DELETE | `/api/admin/blocked-dates` |
| GET | `/api/admin/orders?status=` · GET `/api/admin/orders/{id}` |
| POST | `/api/admin/orders/{id}/approve` · `/api/admin/orders/{id}/reject` `{note}` |

## Order status transitions

| Transition | Endpoint | Allowed actor |
|---|---|---|
| draft → pending_approval | `POST /api/orders/{id}/submit` | Order's customer |
| pending_approval → approved | `POST /api/admin/orders/{id}/approve` | Owner |
| pending_approval → rejected | `POST /api/admin/orders/{id}/reject` | Owner |

Any other transition → `409 invalid_transition`. The AI agent has no tool that triggers these.
