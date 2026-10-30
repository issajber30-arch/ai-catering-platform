# Preliminary Database Schema (PostgreSQL / Supabase)

Status: **Draft v0.1**. Catalog, logistics and availability tables are migrated (Phase 2) with per-language `name_he/ar/en` and `description_he/ar/en` columns on categories and dishes; orders and AI tables are still planned.

Conventions **[RECOMMENDATION]**: `uuid` PKs (`gen_random_uuid()`), `timestamptz` `created_at`/`updated_at`, money as `numeric(10,2)`, enums as Postgres enum types, snake_case, RLS enabled on every table.

## Enums

| Enum | Values | Source |
|---|---|---|
| `pricing_unit` | `per_guest`, `per_tray`, `per_weight`, `per_item` | Decision 6 |
| `kashrut_class` | `meat`, `dairy`, `pareve` | Decision 9 |
| `fulfillment_type` | `pickup`, `delivery` | Decision 8 |
| `order_status` | `draft`, `pending_approval`, `approved`, `rejected`, `cancelled` | Spec §10 (preliminary) |
| `proposal_status` | `pending`, `approved`, `rejected`, `expired`, `failed` | AI design |
| `allergen_status` | `contains`, `free`, `unknown` | Decision 9 — unknown ≠ free |

## Tables

### customers
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| auth_user_id | uuid null unique | FK `auth.users` if accounts are chosen **[OPEN #1]** |
| full_name | text not null | |
| email | text null | |
| phone | text null | |
| created_at, updated_at | timestamptz | |

### events
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK → customers, not null | |
| event_type | text not null | Private event label; list configurable **[RECOMMENDATION]** |
| event_date | date not null | |
| adults | int not null ≥ 0 | |
| children | int not null ≥ 0 | |
| vegetarian_guests | int not null ≥ 0 | Subset semantics **[OPEN #4]** |
| vegan_guests | int not null ≥ 0 | Subset semantics **[OPEN #4]** |
| restricted_guests | int not null ≥ 0 | |
| dietary_notes | text null | Free text, shown to owner; never parsed into safety claims |
| CHECK | `adults + children > 0` | |

### dish_categories
`id` uuid PK · `name` text not null unique · `sort_order` int not null default 0 · `is_active` bool default true

### dishes
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| category_id | uuid FK → dish_categories not null | index |
| name | text not null | |
| description | text null | |
| image_path | text null | Supabase Storage object path |
| pricing_unit | pricing_unit not null | |
| unit_price | numeric(10,2) not null CHECK ≥ 0 | |
| unit_label | text null | e.g., tray size / weight unit text **[OPEN #18]** |
| currency | char(3) not null default from config | **[OPEN #17]** |
| min_quantity | numeric(10,2) null | **[OPEN #15]** |
| is_available | bool not null default true | |
| created_at, updated_at | timestamptz | |

### dish_dietary (1:1 with dishes)
`dish_id` uuid PK/FK → dishes · `kashrut_class` kashrut_class **null** (null = not provided) · `is_vegetarian` bool null · `is_vegan` bool null · `verified_at` timestamptz null

Null booleans mean **unknown** and must be presented as unknown, never as "no"/"yes".

### allergens
`id` smallint PK · `name` text unique (list maintained by owner)

### dish_allergens
`dish_id` FK · `allergen_id` FK · `status` allergen_status not null · PK(`dish_id`,`allergen_id`)
A missing row = **unknown**.

### delivery_zones
`id` uuid PK · `name` text not null · `fee` numeric(10,2) not null ≥ 0 · `definition` jsonb not null (shape depends on **[OPEN #19]**) · `is_active` bool

### time_slots
`id` uuid PK · `fulfillment_type` fulfillment_type · `weekday` smallint 0–6 null · `start_time` time · `end_time` time · `capacity` int null **[OPEN #5]** · `is_active` bool · CHECK `end_time > start_time`

### blocked_dates
`id` uuid PK · `date` date unique · `reason` text null

### orders
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK not null | index |
| event_id | uuid FK not null unique | |
| status | order_status not null default `draft` | index |
| version | int not null default 1 | Incremented on every mutation; optimistic locking for proposals |
| fulfillment_type | fulfillment_type not null | |
| requested_at | timestamptz not null | Requested pickup/delivery time |
| delivery_address | text null | CHECK: required when `delivery` |
| delivery_zone_id | uuid FK null | |
| subtotal, delivery_fee, total | numeric(10,2) null | Computed by backend; frozen at submission |
| submitted_at, decided_at | timestamptz null | |
| decision_note | text null | Owner's note on approve/reject |
| cancelled_at | timestamptz null | Set when the owner cancels |
| cancel_note | text null | Required reason (1-1000 chars), shown to the customer |
| created_at, updated_at | timestamptz | |

### order_items
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| dish_id | uuid FK not null | |
| quantity | numeric(10,2) not null CHECK > 0 | |
| UNIQUE | (`order_id`, `dish_id`) | |
| snapshot_name | text null | **Price snapshot** — filled on submission |
| snapshot_pricing_unit | pricing_unit null | |
| snapshot_unit_price | numeric(10,2) null | |
| snapshot_line_total | numeric(10,2) null | |

While `draft`, prices are read live from `dishes`; on `pending_approval` the snapshot columns become authoritative.

Phase 4 (migration `20261030000001_ai.sql`): `ai_messages` also stores `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `stop_reason` and an identity `seq`; `ai_change_proposals` adds `diff jsonb` and `rationale`; one `pending` proposal per order (partial unique index).

### ai_conversations
`id` uuid PK · `order_id` FK not null · `created_at` · index on `order_id`

### ai_messages
`id` uuid PK · `conversation_id` FK · `role` text CHECK in (`user`,`assistant`,`tool`) · `content` jsonb · `created_at`

### ai_change_proposals
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| conversation_id | uuid FK null | |
| base_order_version | int not null | Must equal `orders.version` at execution |
| changes | jsonb not null | Validated list of typed operations |
| price_before, price_after | numeric(10,2) not null | Computed by backend at proposal time |
| status | proposal_status not null default `pending` | |
| created_at, decided_at, executed_at | timestamptz | `executed_at` set once → idempotency |
| PARTIAL UNIQUE | one `pending` per order? **[RECOMMENDATION]** — simplifies UI | |

## Status transitions **[RECOMMENDATION]**

| From | To | Actor |
|---|---|---|
| draft | pending_approval | Customer (owner of order) |
| pending_approval | approved | Owner |
| pending_approval | rejected | Owner |
| pending_approval, approved | cancelled | Owner |

Proposals may only execute while order is `draft`.

## Business rules storage

`quantity_rules` (Phase 3): `category_id` unique FK · `per_adult`, `per_child` numeric(10,3) ≥ 0 · `round_step` numeric(10,3) > 0 default 1. Need = adults×per_adult + children×per_child, split evenly across the selected dishes of that category and rounded up to `round_step`; `per_guest` dishes suggest adults + children. Values are entered by the owner **[#3]**.

Phase 3 also adds `orders.access_token_hash` (sha256 of the guest token), `orders.time_slot_id`, `orders.currency`; `customers` has no `auth_user_id` yet (guest checkout, #1). `requested_at` is stored in `BUSINESS_TIMEZONE` (default Asia/Jerusalem).

Phase 3.1: `business_settings` (single row, `id boolean PK CHECK (id)`): lead time, food minimum, delivery base/per-km/max-km, kitchen address + lat/lon. `orders` adds `delivery_km`, `delivery_lat`, `delivery_lon`, `delivery_fee_estimated`; the zone requirement is replaced by `orders_delivery_needs_address`. `geocode_cache` (`address_norm` PK, lat, lon, found) caches Nominatim answers, including not-found; lookup failures are never cached.
