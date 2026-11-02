# UX/UI Specification (initial structure)

Status: **Draft v0.1**. High-fidelity prototypes (Claude Artifacts) come in the UI phase; brand, colors, and language are **[OPEN #12, #20]**.

## 0. Implementation status

| Area | Status |
|---|---|
| Language / direction | Hebrew only, RTL (decision #12, see `OPEN_DECISIONS.md`) |
| Customer C1-C5 | Built in `frontend/customer/` + `frontend/js/customer/`, running on a **mock backend** (`js/customer/mock-backend.js`) that mirrors `API_CONTRACTS.md` shapes |
| Admin A1-A5 | Not built yet (placeholder page) |
| Brand (#20) | Still open. Colors are tokens in `css/base.css`; the current forest-green accent is a placeholder |

Known gaps against the spec: the date field is a native `<input type="date">` (blocked dates are validated and listed, not greyed out); quantity formulas, slots, zones, lead time and the allergen disclaimer are placeholders pending #3, #5, #19 and #8; dish images show only when the API supplies `image` (no photos until admin upload exists).

Preview without the backend: `python -m http.server 8000 --directory frontend`, then open `/customer/`. Add `?demo=pending|approved|rejected` to jump straight to the status screen.

## 1. Principles

- Mobile-first; breakpoints 640 / 1024 px **[RECOMMENDATION]**.
- Accessibility target WCAG 2.2 AA: 4.5:1 text contrast, visible focus, 44×44 px touch targets, labels on all inputs, `aria-live` for price totals and chat replies, full keyboard use.
- Direction-agnostic CSS (logical properties: `margin-inline-start`, etc.) so RTL can be enabled without rewrites.
- Premium but calm: generous whitespace, one accent color, restrained motion, `prefers-reduced-motion` respected.
- Never show a pending quotation as a confirmed booking — status badges use explicit text ("Awaiting business approval").

## 2. Design tokens (neutral placeholders)

Defined in `frontend/css/base.css` as CSS custom properties: color (`--color-bg`, `--color-surface`, `--color-text`, `--color-muted`, `--color-accent`, `--color-success`, `--color-danger`, `--color-warning`), spacing scale (4-px based), radius, font stack (system fonts until brand fonts chosen), shadow levels. Dark mode not in scope unless requested.

## 3. Customer screens

| # | Screen | Key elements |
|---|---|---|
| C1 | Event configuration | Stepper; event type, date (blocked dates disabled), time slot, guest composition counters with helper text (subset rule **[OPEN #4]**), dietary notes, pickup/delivery toggle, address + zone fee preview |
| C2 | Dish catalog | Category tabs/chips, dish cards (image, name, price + unit, kashrut badge, veg/vegan badges, "allergen info" link), filters, add/quantity stepper |
| C3 | Order summary & pricing | Itemized lines (qty × unit price = line), recommendation hints, delivery fee, total, `version`-safe edits |
| C4 | AI assistant | Desktop: side panel next to C2/C3. Mobile: bottom sheet opened by a persistent button. Message list, input, proposal cards inline |
| C5 | Quote submission & status | Review, explicit "Submit quotation request", status page: Draft / Awaiting approval / Approved / Rejected + owner note |

### Proposal diff card (C4)

```
┌ Suggested change ───────────────────────┐
│ Add  Roasted vegetables        × 2 trays │
│ Hummus             3 → 5 trays           │
│ ─────────────────────────────────────── │
│ Total   1,200.00  →  1,350.00  (+150.00) │
│ [ Reject ]                   [ Approve ] │
└──────────────────────────────────────────┘
```
States: pending, applying, applied, rejected, expired ("Your order changed; ask again"). Approve is the only path to mutation.

## 4. Admin screens

| # | Screen | Key elements |
|---|---|---|
| A1 | Order management | Filter by status, list with event date/guests/total, detail with frozen snapshot, Approve / Reject + note |
| A2 | Dishes & categories | Table/cards, create/edit form, image upload, dietary + allergen editor with explicit Unknown option |
| A3 | Pricing configuration | Pricing unit, unit price, unit label per dish; bulk view |
| A4 | Availability | Calendar of blocked dates; capacity **[OPEN #5]** |
| A5 | Pickup & delivery | Time slots per weekday and type; delivery zones with fees |

## 5. Frontend structure

```
frontend/
  customer/index.html   # C1–C5 (single page, JS-driven steps)
  admin/index.html      # A1–A5
  css/base.css          # tokens, reset, primitives
  js/api.js             # fetch wrapper, error format handling
  assets/
```
Reusable components as small ES modules (e.g., `js/components/dish-card.js`) added in later phases.
