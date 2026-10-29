# AI Catering Platform

Ordering and management web app for a **single catering business**. Customers plan private events, pick dishes, get backend-calculated quantities and prices, and chat with an AI assistant whose suggested changes only apply after the customer approves them. The business owner manages the catalog and approves or rejects every quotation.

> Status: **Phase 3 — customer ordering**. Customers plan an event, pick dishes, see suggested quantities and a server-calculated price, and send a quote request via a private link; the owner approves or rejects it in the admin. The AI assistant comes in Phase 4. See `docs/` for the specs.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2 |
| Frontend | Plain HTML, CSS, JavaScript (served by FastAPI) |
| Data | Supabase (Postgres, Storage, Auth when approved) |
| Hosting | Railway (Dockerfile build) |
| Quality | pytest, Ruff, GitHub Actions |

## Repository layout

```
backend/        FastAPI app (api, core, models, schemas, services, repositories, agents) + tests
frontend/       customer/ and admin/ pages, css/, js/, assets/
database/       migrations/ (SQL, Supabase CLI format)
docs/           PRD, architecture, schema, API, AI agent, UX/UI, ADRs, open decisions
.github/        CI workflow
Dockerfile      Production image used by Railway
railway.json    Railway build/deploy config (healthcheck /health)
.env.example    Environment variable template
```

## Local development

Requires [uv](https://docs.astral.sh/uv/) (it installs a matching Python automatically).

```bash
cp .env.example .env          # fill values when needed; .env is git-ignored
cd backend
uv sync                       # install dependencies
uv run uvicorn app.main:app --reload
```

- API health: http://127.0.0.1:8000/health
- Customer UI: http://127.0.0.1:8000/customer/
- Admin UI: http://127.0.0.1:8000/admin/

### Database setup (local Postgres 16)

```bash
createdb catering_dev && createdb catering_test
psql catering_dev -f database/migrations/20261029000001_catalog.sql
# .env: DATABASE_URL=postgresql+psycopg://localhost/catering_dev
#       TEST_DATABASE_URL=postgresql+psycopg://localhost/catering_test
```

The tests drop and recreate the `public` schema of `TEST_DATABASE_URL` and apply every migration, so use a dedicated database.
To apply a migration to Supabase: `psql "$DATABASE_URL" -f database/migrations/<file>.sql` (use the direct or session connection string).

### Admin login (Supabase Auth)

1. In the Supabase dashboard create the owner user (Authentication, Users) with an email and password.
2. Make that user an admin once, in the SQL editor (`app_metadata` cannot be edited by the user):
   `update auth.users set raw_app_meta_data = raw_app_meta_data || '{"role":"admin"}' where email = 'owner@example.com';`
3. Create a **public** Storage bucket named `dish-images`.
4. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`, then open `/admin/`.

The backend verifies the token against the project's JWKS (ES256/RS256) and requires `app_metadata.role == "admin"`.
The admin token lives in `sessionStorage` with no refresh flow, so log in again after it expires.

### Tests and lint

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Dependencies and why

| Package | Why |
|---|---|
| `fastapi` | Mandated web framework |
| `uvicorn[standard]` | ASGI server for FastAPI |
| `pydantic-settings` | Typed config from environment variables |
| `sqlalchemy` | ORM and queries (ADR 0002) |
| `psycopg[binary]` | Postgres driver for SQLAlchemy |
| `pyjwt[crypto]` | Verify Supabase JWTs (JWKS, ES256/RS256) |
| `python-multipart` | Parse dish image uploads |
| `httpx` | Supabase Storage REST upload (also used by FastAPI's `TestClient`) |
| `pytest` (dev) | Mandated test runner |
| `ruff` (dev) | Mandated linter/formatter |

The Supabase Python client is not used: JWKS, Auth REST and Storage REST are called directly.

## Branches and environments

| Branch | Purpose | Railway env | Supabase project |
|---|---|---|---|
| `main` | Production (default branch) | `production` | prod project |
| `dev` | Integration | `development` | dev project |

- Feature work → PR into `dev` (CI must pass).
- Release → PR `dev` → `main`.
- Production deploys are manual and need explicit approval.
- Each Railway environment holds its own variables from `.env.example`. **Never commit secrets.** The service-role key stays server-side.

## Railway / Supabase status

Configuration templates only (`railway.json`, `Dockerfile`, `.env.example`). No Railway project or Supabase project is connected yet. That is planned for Phase 6.

## Documentation

- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Database schema](docs/DATABASE_SCHEMA.md) · [API contracts](docs/API_CONTRACTS.md)
- [AI agent design](docs/AI_AGENT_DESIGN.md) · [UX/UI spec](docs/UX_UI_SPEC.md) · [Open decisions](docs/OPEN_DECISIONS.md) · [ADRs](docs/ADR/)
