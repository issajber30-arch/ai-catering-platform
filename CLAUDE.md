# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An ordering and management web app for **one** catering business that serves private events. Customers build an order and get a backend-calculated quote. An AI assistant may only *propose* changes, which apply after the customer approves them. The owner approves or rejects every quote. Specs are in `docs/`: PRD, ARCHITECTURE, DATABASE_SCHEMA, API_CONTRACTS, AI_AGENT_DESIGN, UX_UI_SPEC and ADRs. Work proceeds in numbered phases. Check the phase noted in `README.md` and the docs before building something from a later phase.

`docs/OPEN_DECISIONS.md` lists business questions that engineering must **not** answer itself (serving formulas, VAT, delivery zones, kashrut, auth for customers…). When a feature depends on an open decision, store the data loosely (nullable column, free `jsonb`) and say so. Never invent the rule. Record answered decisions in that file's decision log.

## Commands

All backend commands run from `backend/` and need [uv](https://docs.astral.sh/uv/) and a local Postgres 16. On this machine that's Postgres.app, with binaries in `/Applications/Postgres.app/Contents/Versions/16/bin`.

```bash
uv sync
uv run uvicorn app.main:app --reload            # http://127.0.0.1:8000  (/admin/, /customer/, /health)
uv run ruff check . && uv run ruff format --check .
TEST_DATABASE_URL=postgresql+psycopg://localhost/catering_test uv run pytest
uv run pytest tests/test_security.py::test_admin_routes_reject_anonymous   # single test
psql catering_dev -f ../database/migrations/<file>.sql                    # apply a migration
```

- The test fixture (`tests/conftest.py`) **drops the `public` schema** of `TEST_DATABASE_URL` and re-applies every file in `database/migrations/` in name order. It refuses any database whose name doesn't end in `_test`.
- Each test truncates the tables named in `TABLES` in `conftest.py`. **Add every new table there** when you add a migration, or data leaks between tests.
- Settings load from `.env` in `backend/` or the repo root (`core/config.py`), so pytest picks up `TEST_DATABASE_URL` from there too.
- Tests fake Supabase entirely: a local ES256 key pair, a monkeypatched JWKS client and a fake storage uploader. They never need network access.
- CI (`.github/workflows/ci.yml`) runs on Python 3.12 with a `postgres:16` service and runs `uv sync --frozen` → ruff check → ruff format check → pytest. Changing dependencies means committing an updated `uv.lock`.
- Ruff: line length 100, rules `E,F,I,B,UP,S` (bandit), with `S101` allowed in tests.

## Architecture

There's one FastAPI app (`backend/app/main.py`) that serves the JSON API and also mounts `frontend/` as static files **last**, so API routes win. Being same-origin means there's no CORS.

The layers are strict, and lower layers never import upper ones:
`api/` (routers) → `services/` (business rules) → `repositories/` (queries) → `models/` (SQLAlchemy 2 ORM). `schemas/` holds the Pydantic DTOs, and `core/` holds config, DB session, errors, auth and storage. `agents/` (Phase 4) may call **services only**, through typed tools, never the database.

Rules that span several files:
- **The backend is authoritative.** Prices, quantities, order state and availability are computed server-side. Neither the frontend nor the LLM is trusted for them (ADR 0003).
- **Error shape:** every error is `{"error": {"code", "message", "details"}}`. Raise `core.errors.AppError(status, message)`, whose code comes from the status via `CODES`. 422 responses deliberately drop the submitted input values.
- **Admin auth:** `api/admin.py` uses one router-level `Depends(require_admin)`, and a test walks `app.routes` to enforce it on every `/api/admin/*` route. `core/security.py` verifies Supabase JWTs through the project's JWKS. The algorithms are fixed to ES256/RS256 and `aud`/`iss`/`exp` are required. Admin = `app_metadata.role == "admin"`.
- **Unknown ≠ no:** null dietary booleans and missing `dish_allergens` rows mean *unknown*. They must reach the client as `null` / `"unknown"`, never as `false`.
- **Languages:** the UI is in Arabic, Hebrew and English, with RTL for ar/he. Catalog text is stored as per-language columns (`name_he` required, `name_ar` and `name_en` falling back to Hebrew). The frontend CSS uses logical properties only.
- **Money:** `numeric(10,2)` plus a per-row `currency`. The default `ILS` comes from `DEFAULT_CURRENCY`.
- **Images:** the type is detected from magic bytes (JPEG/PNG/WebP), the size cap is 5 MB, and the name is server-generated. Files upload to the public Supabase Storage bucket `dish-images` with the service-role key, which stays server-side. A middleware in `main.py` rejects oversized bodies before multipart parsing and auth.
- **Delivery fee** comes from `services/geo.py`: Nominatim at a fixed host (never build the URL from input), 1 request/s process-wide with a 3 s fail-fast, results cached in `geocode_cache`. Geocode **before** taking an order's row lock (the cache commits). Tests override `get_geocoder`; they never hit the network.
- **Rate limits** (`core/ratelimit.py`): per client IP (rightmost `X-Forwarded-For`), in process memory, so they reset on restart and are per instance (`shortcut:` move to Redis/DB before scaling out). Applied as `Depends(limit(...))` on order create, delivery quote and chat; a test fixture resets them. The delivery quote is POST so addresses never appear in URLs or access logs.
- **Security headers** (CSP with `script-src 'self'`, no inline scripts; `frame-ancestors 'none'`; `no-referrer`) are set in `main.py`. Pages must not use inline `<script>` or `on*=` attributes.
- **AI assistant** (`agents/`): calls services only. The model gets read tools and one `propose_order_change` tool; it can never mutate an order, change status or prices. Customer name, contact details, address and owner notes never reach the model; untrusted text goes in as `{text, source}`. The system prompt in `agents/prompt.py` is frozen (prompt cache). Tests override `get_llm()` with a fake and never call the API. Nullable enums in tool schemas must use `anyOf` (a test enforces it).
- **Deploy:** Render builds the `Dockerfile` from `render.yaml` (dev site from `dev`). On start the container runs `python -m app.migrate`, which applies unapplied `database/migrations/*.sql` once each (tracked in `schema_migrations`). Local `catering_dev` predates that table, so keep applying migrations there with `psql`. Secrets are `sync: false` in `render.yaml` and set only in Render's dashboard. `DATABASE_URL` must be Supabase's session-pooler string (the direct host is IPv6-only).
- **Migrations** are plain SQL files in `database/migrations/` named `YYYYMMDDHHMMSS_<name>.sql`. RLS is enabled on every table with no policies, because the backend connects as a privileged role.

The frontend is plain HTML/CSS/ES modules with no framework and no build step. `frontend/js/api.js` is the shared fetch wrapper: it adds the Bearer token and turns the error shape into thrown errors. The admin dashboard (`frontend/admin/admin.js`) builds the DOM with `createElement`/`textContent` through its `h()` helper. Never use `innerHTML` with data. Admin login calls Supabase Auth REST directly, using the anon key from `GET /api/public-config`.

## Branches

`main` = production and `dev` = integration. Feature branches open a PR into `dev`, and CI must pass. A release is a PR from `dev` into `main`. Production deploys (Render) are manual and need explicit approval. This checkout is a fork: `origin` = `issajber30-arch/ai-catering-platform` and `upstream` = `JonathanZouari/ai-catering-platform`.
