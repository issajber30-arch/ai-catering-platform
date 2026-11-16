# Lead scoring with linear regression — design

Date: 2026-11-16 · Branch: `feature/lead-regression` (from `dev`)

## Intent
The owner of a CaterKing catering business wants to know, when a new lead comes in, **how likely it is
that this potential customer will place an order**, so they know whom to follow up first.
The owner explicitly chose **linear regression with the output clipped to 0–100%** (a linear
probability model) over logistic regression, knowing the trade-off. The model is trained on
**synthetic data**. The UI must look like the rest of the platform (Pit Wall, dark F1 admin).

## Goals
1. A `leads` table and admin API for leads (list, create, get one, update status, delete).
2. A linear regression (OLS) fitted on a synthetic history of past leads with a known outcome
   (ordered / did not order). Score = `clip(prediction, 0, 1)`, shown as a percentage.
3. A new admin tab **QUALIFYING** in the Pit Wall: tiles by chance band, a Timing-Tower-style list of
   leads sorted by chance, a lead detail view with the per-feature breakdown, and a manual
   "new lead" form (e.g. someone who phoned).
4. A small model card on the tab: R², share of predictions that were clipped, accuracy at 50%, and the
   number of synthetic training rows. It states plainly that the model is trained on synthetic data.
5. A button to add demo (synthetic) leads, so the tab is not empty on a fresh database.

## Non-goals
- No customer-facing lead capture form (option B, possible later).
- No tracking of abandoned orders or site behaviour.
- No retraining on real outcomes (statuses are stored so this can come later).
- No logistic regression or other models.
- No new ML dependency (numpy/scikit-learn): OLS on ~10 features is a few lines of pure Python.

## Anti-goals
- Synthetic leads silently mixed into real data: every demo lead has `is_demo = true` and is shown
  with a DEMO chip; demo leads are never created automatically (only by the explicit button).
- A score shown as above 100% or below 0%.
- Any lead personal data (name, phone, email, notes) reaching the AI assistant or logs.
- Breaking the existing layers, the admin auth test, or the security headers (no inline scripts,
  no `innerHTML` with data).

## Approaches considered
| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Admin-only QUALIFYING tab; leads entered by the owner or generated as demo | Smallest; fits "synthetic data" and the existing design; B can be added on top later |
| B | A + a public "leave your details" form on the customer site | Twice the work: public endpoint, rate limit, spam protection, ar/he/en, privacy |
| C | Infer leads from abandoned orders | Needs behaviour tracking + privacy review; dropped |

On the model: logistic regression is the right tool for a probability; the owner chose clipped
linear regression knowingly. The UI shows the clip honestly (the model card shows the clipped share).

## Lead features (the model inputs)
| Field | Type | Notes |
|---|---|---|
| `event_type` | one of `EVENT_TYPES` (`birthday, family_celebration, bar_bat_mitzvah, shabbat, other`) | reuse the existing tuple |
| `guests` | int 1–1000 | |
| `days_until_event` | derived from `event_date` (date) at scoring time | stored as a date, not a number |
| `source` | `instagram, google, referral, whatsapp, phone, other` | new tuple |
| `returning_customer` | bool | |
| `used_assistant` | bool | talked to the AI assistant |
| `requested_quote` | bool | asked for a price quote |
| `budget_per_guest` | numeric(10,2), nullable | ILS; unknown → mean-imputed for scoring and shown as "unknown" |

Personal fields stored but **not** model inputs: `full_name` (required), `phone`, `email`, `notes`.
`status`: `new, contacted, won, lost` (default `new`). `is_demo` bool. `created_at`, `updated_at`.

## Model
- **Synthetic history**: generated deterministically in code (fixed seed), ~800 rows, from a
  documented "true" logistic process with plausible effects (referral and returning customers
  convert more; very short or very long lead times convert less; bar/bat mitzvah and weddings-size
  events have higher intent; asking for a quote and using the assistant raise intent). The generator
  is the single source of truth and lives in one module with its coefficients written out.
- **Encoding**: one-hot for `event_type` and `source` (drop one level), booleans as 0/1, `guests`
  and `budget_per_guest` as is, `days_until_event` plus a squared term (so "too soon" and
  "too far" can both lower the chance — the one non-linearity the owner will notice).
- **Fit**: OLS via normal equations in pure Python, fitted once per process on first use and
  cached. Deterministic → the same scores across restarts and instances.
- **Explanation**: for a linear model the contribution of a feature is `coef × (x − mean_x)` in
  percentage points relative to the average lead; one-hot groups are summed back to the original
  field. The detail view shows them as a bar list ("returning customer +18 pts").
- **Scores are computed on read**, never stored, so they cannot go stale.

## API (admin, under the existing router-level `require_admin`)
- `GET /api/admin/leads` → leads with `chance` (0–1), `raw_prediction`, `clipped` flag; sorted by chance.
- `POST /api/admin/leads` → create (validated with Pydantic; enums, ranges, max lengths).
- `GET /api/admin/leads/{id}` → lead + breakdown.
- `PATCH /api/admin/leads/{id}` → status / fields.
- `DELETE /api/admin/leads/{id}`; `DELETE /api/admin/leads/demo` removes all demo leads.
- `POST /api/admin/leads/demo` → add N (default 12, max 50) demo leads.
- `GET /api/admin/leads/model` → model card.
Errors use the existing `{"error": {...}}` shape via `AppError`.

## Data
- Migration `database/migrations/20261116000001_leads.sql`; RLS enabled, no policies (house rule).
- Add `leads` to `TABLES` in `tests/conftest.py`; add the model so the SQLite path works
  (`migrate.create_sqlite_schema` builds from models).

## UI (Pit Wall look)
New top-level group `QUALIFYING` ("לידים") in `GROUPS` in `frontend/admin/admin.js`, built with the
existing `h()` helper and existing classes (`tiles`/`tile`, `panel tower`, `rows`/`row`, `chip`,
`card`, `num`). Hebrew labels, RTL, logical CSS properties only. Any new CSS goes in `admin.css`.
- Tiles: `POLE` (≥70%), `POINTS` (40–69%), `BACK OF THE GRID` (<40%), `NEW TODAY`.
- Tower: `P1…Pn` by chance, name (first name only, as in the orders tower), event type, guests,
  date, source, chance with a bar, status chip, DEMO chip where relevant.
- Detail: fields, status buttons, breakdown bars (green raises, red lowers), "clipped at 100%" note.
- New-lead form; "add demo leads" button; model card.

## Testing
- Unit: OLS recovers known coefficients on noiseless data; clip keeps 0 ≤ chance ≤ 1; the breakdown
  sums to `raw_prediction − mean prediction`; a referral returning customer with a quote scores higher
  than a cold Instagram lead with an event in 2 days; missing budget handled.
- API: create/list/get/patch/delete; validation errors are 422 without echoing input; demo cap 50;
  the existing admin-auth route walker covers the new routes automatically.
- E2E: run the app locally, log in to the admin, open QUALIFYING, add demo leads, add a manual lead,
  open a lead, change status.
- CI: ruff + ruff format + pytest on Postgres.

## Calls made after the builder review (my calls, correctable)
1. `used_assistant`, `requested_quote`, `returning_customer` are plain checkboxes the owner ticks.
   No link to `ai_conversations`, no PII matching.
2. The synthetic "true" process is a **noisy** logistic process; effects are plausible placeholders,
   not business facts (stated on the model card). Target: moderate R² (~0.3–0.5) and a non-zero
   clipped share, so the clip is visible.
3. Model card metrics come from a fixed-seed 80/20 holdout of the synthetic history; the model used
   for scoring is then refit on all rows.
4. Demo leads are drawn from the same generator's feature distribution, with names from a fixed
   fake-name list, status `new`, `created_at` = now, `is_demo = true`. A "delete all demo leads"
   action is included (`DELETE /api/admin/leads/demo`) so the owner can clean up.
5. `won`/`lost` leads stay in the list (sorted after open leads) but are excluded from the band tiles.
6. `event_date` is required and must be today or later at create/update; at scoring time
   `days_until_event` is clamped to the training range (0–365).
7. "NEW TODAY" counts `created_at` in Asia/Jerusalem, matching the existing admin `TZ`.
8. Fixed paths (`/leads/model`, `/leads/demo`) are registered before `/leads/{id}`.

## Left to the builder
Exact synthetic coefficients, chip colours within existing tokens, copy text, file split inside
`services/` (e.g. `services/leads.py` + `services/lead_model.py`).
