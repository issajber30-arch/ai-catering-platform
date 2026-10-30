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

## Customer orders (Phase 3, implemented)

Guest checkout (decision #1). `POST /api/orders` returns `access_token` once; every other customer route needs header `X-Order-Token`. A missing/wrong token and an unknown id both return 404. Customer routes accept `?lang=he|ar|en`. Public helpers: `GET /api/catalog/event-types`, `GET /api/public-settings` → `{lead_time_days, min_food_total, max_km}`, `POST /api/delivery-quote {address}` (1–500 chars; POST so the address stays out of URLs and logs) → `{found, km, fee, max_km, too_far}`. `GET /api/delivery-zones` remains for legacy zone orders only.

Phase 3.1 rules (server-enforced): event date ≥ today + `lead_time_days` (422 "Events need at least N days' notice"); submit needs food subtotal ≥ `min_food_total` (422); delivery fee = base + per_km × straight-line km from the kitchen, max `delivery_max_km` (422 "choose pickup"); address not found → `delivery_fee: null`, `delivery_fee_estimated: true`, total excludes delivery. `OrderOut` adds `warnings` (`"mixes_meat_dairy"`), `delivery_km`, `delivery_fee_estimated`. Every response carries CSP, `X-Content-Type-Options`, `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY`. `time_slots.weekday`: Monday=0 … Sunday=6, null = any day.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders` | Create draft from event config |
| GET | `/api/orders/{id}` | Order with items, live pricing, `version` |
| PATCH | `/api/orders/{id}` | Update event/fulfillment details; requires `version` |
| PUT | `/api/orders/{id}/items/{dish_id}` | Set quantity; requires `version` |
| DELETE | `/api/orders/{id}/items/{dish_id}` | Remove dish; requires `version` |
| GET | `/api/orders/{id}/pricing` | Itemized breakdown |
| GET | `/api/orders/{id}/recommendations` | Quantity recommendations (rules **[OPEN #3]**) |

Rate limits (per client IP, in memory; 429 `rate_limited` + `Retry-After`): `POST /api/orders` 10/hour, `POST /api/delivery-quote` 30/10 min, `POST /api/orders/{id}/chat` 60/hour.
| POST | `/api/orders/{id}/submit` | `draft → pending_approval`; freezes snapshot |

Every mutation returns the full updated order (new `version`). A stale `version` → `409 order_version_conflict`.

## AI assistant (Phase 4, implemented)

All routes need `X-Order-Token`; chat works only on `draft` orders. Errors: 409 `proposal_not_pending`, 409 `order_version_conflict` (proposal becomes `expired`), 409 `conflict` (assistant still answering), 429 `rate_limited`, 413 (chat body > 16 KiB), 503 "The assistant is unavailable right now. Your order is unchanged." `GET /api/orders/{id}/chat` returns visible messages `[{id, role, text, created_at}]`. Proposals also carry `diff: [{dish_id, name, current, proposed}]` and `rationale`. Owner: `GET /api/admin/orders/{id}/assistant` → `{message_count, last_message_at, proposals}` (no chat text by design).

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
| GET/POST/PATCH/DELETE | `/api/admin/delivery-zones` (legacy; tab hidden since Phase 3.1) |
| GET/PUT | `/api/admin/settings` `{lead_time_days, min_food_total, delivery_base_fee, delivery_per_km, delivery_max_km, kitchen_address}`; a changed address is geocoded, unknown → 422 |
| GET/POST/PATCH/DELETE | `/api/admin/time-slots` |
| GET/POST/DELETE | `/api/admin/blocked-dates` |
| GET | `/api/admin/orders?status=` · GET `/api/admin/orders/{id}` |
| GET | `/api/admin/quantity-rules` · PUT/DELETE `/api/admin/quantity-rules/{category_id}` `{per_adult, per_child, round_step}` |
| POST | `/api/admin/orders/{id}/approve` · `/api/admin/orders/{id}/reject` `{note}` |
| POST | `/api/admin/orders/{id}/cancel` `{note}` (required, 1-1000 chars after trim; 409 `invalid_transition` unless pending_approval or approved) |

## Order status transitions

| Transition | Endpoint | Allowed actor |
|---|---|---|
| draft → pending_approval | `POST /api/orders/{id}/submit` | Order's customer |
| pending_approval → approved | `POST /api/admin/orders/{id}/approve` | Owner |
| pending_approval → rejected | `POST /api/admin/orders/{id}/reject` | Owner |
| pending_approval or approved → cancelled | `POST /api/admin/orders/{id}/cancel` | Owner |

Any other transition → `409 invalid_transition`. The AI agent has no tool that triggers these.
