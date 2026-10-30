# Product Requirements Document — AI Catering Platform (MVP)

Status: **Draft v0.1** · Phase 0 deliverable

Legend: **[CONFIRMED]** = mandated by the business spec · **[RECOMMENDATION]** = engineering proposal, changeable · **[OPEN]** = needs a business decision (see `OPEN_DECISIONS.md`).

---

## 1. Purpose

A web application for **one** catering business that lets private customers build a catering order, get a deterministic price quotation, and get help from an AI assistant that can *propose* (never silently apply) changes to their order. The business owner manages the catalog and approves or rejects every quotation.

## 2. Users

| Persona | Description | Interface |
|---|---|---|
| Customer | A private individual planning a private event (birthday, family celebration, Bar/Bat Mitzvah, Shabbat, …) | Customer application |
| Business owner | Runs the single catering business; manages menu, pricing, logistics, and approves quotations | Admin dashboard |

No other roles are in scope. **[CONFIRMED]** (Decisions 1, 3, 10)

## 3. Confirmed decisions (summary)

| # | Decision | Product implication |
|---|---|---|
| 1 | Single business | No tenants, no vendors, no multi-business admin |
| 2 | Owner approval | Customer submits a quotation; only the owner approves/rejects; AI can never approve |
| 3 | Private events only | No B2B, corporate accounts, invoicing, procurement |
| 4 | Free menu selection | Customer picks from the owner-managed catalog; AI may recommend existing dishes only |
| 5 | Quantity calculation | Recommended quantities from guest composition via configurable business rules — formulas **[OPEN]** |
| 6 | Mixed pricing | Per guest / per tray / per weight unit / per item; separate delivery fee; deterministic backend calculation |
| 7 | Proactive AI with explicit approval | AI proposes; customer approves each change; backend executes |
| 8 | Pickup & delivery | Dates/times, delivery zones, delivery fees; no staff/on-site service |
| 9 | Basic dietary info | Meat/dairy/pareve, vegetarian, vegan, known allergens; unknown ≠ allergen-free |
| 10 | Full admin dashboard | Dishes, categories, prices, units, descriptions, images, dietary info, orders, approvals, availability, blocked dates, time slots, delivery zones/fees |

## 4. Customer flow **[CONFIRMED]**

1. **Event configuration** — event type, event date, requested pickup/delivery time, guest composition (adults, children, vegetarian, vegan, other dietary restrictions), dietary requirements, pickup or delivery, delivery address when applicable.
2. **Menu browsing** — categories → dishes with price, pricing unit, dietary properties, image, description.
3. **Quantity recommendation** — backend-computed from configured rules.
4. **Pricing** — itemized calculation, total updates after every approved change.
5. **AI assistance** — chat panel embedded in the ordering flow, with access to the current order through controlled backend operations.
6. **Quote submission** — order becomes a quotation request (`pending_approval`).
7. **Business approval** — owner approves/rejects. A pending quotation is never shown as a confirmed booking.

## 5. Admin capabilities **[CONFIRMED]**

- CRUD dishes and categories; descriptions and images (Supabase Storage).
- Prices and pricing units.
- Dietary metadata.
- View orders; approve/reject quotations.
- Availability and blocked dates.
- Pickup and delivery time slots.
- Delivery zones and delivery fees.

No admin AI agent. **[CONFIRMED]**

## 6. AI assistant requirements **[CONFIRMED]**

Can: answer questions about available dishes, recommend existing dishes, flag potentially missing categories, suggest quantity adjustments, explain pricing impact, flag known dietary conflicts, propose add/remove dish, propose quantity changes, propose order-detail updates.

Must not: invent dishes, prices, dietary properties, availability; modify an order without explicit customer approval; approve orders; treat unknown allergen data as safe.

Details: `AI_AGENT_DESIGN.md`.

## 7. Order states **[RECOMMENDATION]** (preliminary, per spec §10)

`draft → pending_approval → approved | rejected`. No payment, cancellation, or revision states without approval.

## 8. Non-functional requirements

| Area | Requirement | Tag |
|---|---|---|
| Source of truth | Database/backend authoritative for prices, quantities, order state | CONFIRMED |
| Determinism | All pricing/quantity math in backend code, not the LLM | CONFIRMED |
| Security | Secrets in env vars only; typed validation on every state change; no arbitrary DB ops from model output | CONFIRMED |
| UX | Mobile-first, responsive, accessible (WCAG 2.2 AA target), premium look | CONFIRMED / target RECOMMENDATION |
| Quote integrity | Price snapshot at submission | CONFIRMED |
| Testing | pytest, Ruff, API integration tests, AI action validation tests | CONFIRMED |
| Environments | `dev` → Render dev + Supabase dev; `main` → Render prod + Supabase prod (hosting changed from Railway, decision log 2026-10-30) | CONFIRMED (separate Supabase projects strongly preferred) |

## 9. Out of scope **[CONFIRMED]**

Multi-business marketplace · admin AI agent · corporate customers · staff/waiter management · advanced inventory · supplier procurement · accounting/invoicing · payment gateway · calorie/nutrition database · automated dish generation · autonomous order approval · native mobile apps.

Unresolved and **not** to be built until decided: serving utensils/disposables, alcohol, voice AI, customer auth method, notifications, cancellation/refund, owner-proposed revisions, post-submission customer edits.

## 10. Success criteria for MVP (proposed) **[RECOMMENDATION]**

- A customer can build and submit a quotation end-to-end on a phone.
- Every AI-originated change appears as a diff card and executes only after approval, exactly once, against the current order version.
- Owner can manage the full catalog and approve/reject quotations without developer help.
- Submitted quotations are unaffected by later catalog price changes.
