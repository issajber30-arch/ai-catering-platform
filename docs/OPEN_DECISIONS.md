# Open Business Decisions

These must be answered by the business before the dependent features are built. Engineering will not invent answers. Unrelated infrastructure work continues meanwhile.

Format: **Question** · *Why it matters* · **Blocks**

| # | Topic | Question | Why it matters | Blocks |
|---|---|---|---|---|
| 1 | Customer authentication / guest checkout | Must customers create an account? Email magic link, OTP by phone, password, or guest checkout with a tokenized link? | Determines ownership model, RLS policies, and how a customer returns to a draft/quote | Phase 3 order ownership, Phase 4 chat history |
| 2 | Payment & deposit | Is any deposit or payment collected in-app? | Payments are out of scope unless approved | Nothing in MVP unless approved |
| 3 | Serving & quantity formulas | Per category/dish, how much per adult / child? Rounding (e.g., whole trays)? Different for vegetarian/vegan guests? | Quantity recommendation must use business rules, not AI guesses | Phase 3 quantity engine (schema can hold rules; values unknown) |
| 4 | Overlapping guest dietary categories | Are vegetarian/vegan/restricted guests counted *within* adults/children (subsets) or separately? Is vegan a subset of vegetarian? | Prevents double-counting | Phase 3 guest composition validation |
| 5 | Availability & capacity | Max orders/guests per day or per slot? Lead time? Same-day orders? | Defines date/slot validation | Phase 2 availability rules, Phase 3 date picker |
| 6 | Quote modification & negotiation | Can the owner edit or counter-propose a quote, or only approve/reject? | Adds states and UI | Out of MVP until decided |
| 7 | Cancellation & revision | Can a customer cancel or edit after submission or approval? Deadlines? | Adds states and rules | Out of MVP until decided |
| 8 | Allergen verification & cross-contamination | What disclaimer text is shown? Is there a "may contain" level? Who verifies allergen data? | Safety and liability wording | Phase 2 allergen fields' semantics, Phase 4 agent wording |
| 9 | Kashrut certification | Which certification(s)? Shown per dish or business-wide? Mixing meat & dairy dishes in one order allowed? | Affects data model and validation | Phase 2 dish fields, Phase 3 conflict checks |
| 10 | Disposable serving equipment | Are utensils/disposables orderable? Priced how? | Could be catalog items or separate | Out of MVP until decided |
| 11 | Alcohol | Offered at all? Age verification? | Legal implications | Out of MVP until decided |
| 14 | VAT & rounding | Are catalog prices VAT-inclusive? VAT rate handling? Rounding rules for totals and weight-based prices? | Deterministic pricing correctness | Phase 3 pricing engine final rules |
| 15 | Minimum order quantities | Minimum per dish, per order, or minimum guests? Minimum for delivery? | Validation rules | Phase 2/3 validation |
| 16 | LLM provider | Which model provider (e.g., Anthropic Claude) and budget? | API keys, tool-calling format, cost | Phase 4 |
| 18 | Weight unit | kg, 100 g, or configurable per dish? | Per-weight pricing math | Phase 2 pricing units |
| 19 | Delivery zone definition | Zones by city list, postal code, or radius/polygon? | Address → zone lookup method | Phase 2 delivery zones |
| 20 | Brand | Business name, logo, colors, fonts | Visual identity | Phase 3 UI polish (neutral tokens until then) |

## Decision log

When a decision is made, record it here and move the row out of the table above.

| Date | # | Decision | Decided by |
|---|---|---|---|
| 2026-10-29 | 12 | Interface languages: Arabic, Hebrew and English; RTL for ar/he | Owner |
| 2026-10-29 | 13 | No notifications; quote requests are viewed on the admin page | Owner |
| 2026-10-29 | 17 | ILS (₪) | Owner |
