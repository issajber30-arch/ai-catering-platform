# Product

<!-- impeccable:product-schema 1 -->

<!-- Source: docs/PRD.md and the project owner's chat messages. No interview round was answered, so every fact below is repo-derived or marked [inferred]. -->

## Platform

web

## Stack

Existing codebase: plain HTML, CSS and JavaScript ES modules served by FastAPI (`frontend/`). No build step.

## Users

- Customer: a private individual planning a private event (birthday, family celebration, Bar/Bat Mitzvah, Shabbat). Mobile-first; often on a phone. Hebrew speaker. [inferred from Hebrew-only decision]
- Business owner: runs the single catering business and approves or rejects every quotation through an admin dashboard.

## Product Purpose

Lets a customer build a catering order, see a deterministic backend-calculated price, and get help from an AI assistant that only proposes changes. The owner approves or rejects each quotation. Success: a customer submits a quotation end-to-end on a phone, and a pending quotation is never mistaken for a confirmed booking.

## Positioning

The AI assistant never changes an order without the customer's explicit approval of a visible diff, and prices come from the backend, not the model.

## Operating Context

Single business. Dishes carry kashrut (meat, dairy, pareve), vegetarian and vegan info, and known allergens; unknown allergen data is never shown as safe. Pricing units: per guest, per tray, per kg, per item, plus a separate delivery fee. Currency shown as ILS (open decision #17).

## Capabilities and Constraints

- Hebrew only, right-to-left (decided 2026-10-29).
- WCAG 2.2 AA target: 4.5:1 text contrast, visible focus, 44px touch targets, `aria-live` for price totals and chat replies.
- Customer flow: event details, menu, order summary, AI assistant, quotation submission and status.
- Undecided: brand name and logo (#20), customer auth (#1), quantity formulas (#3), allergen disclaimer wording (#8).

## Brand Commitments

Business name: **yumm.ai** (confirmed by the project owner, 2026-10-31); logo and final colors are still undecided (#20). The Green Eggs and Ham option adopts a whimsical illustrated storybook identity with the V3 mascot as a concept stand-in; the mascot is uncleared for commercial use.

## Evidence on Hand

No real photography, logo, testimonials or customer data exist. Do not fabricate them. Dish names and prices in the UI are mock data.

## Product Principles

1. The customer always sees what will change before it changes.
2. A quotation request is never presented as a confirmed order.
3. Unknown dietary or allergen data is stated plainly, never implied safe.
4. The first phone screen of every step must be usable without scrolling to find the next action.

## Accessibility & Inclusion

WCAG 2.2 AA, full keyboard use, `prefers-reduced-motion` respected, logical CSS properties so direction never needs a rewrite.
