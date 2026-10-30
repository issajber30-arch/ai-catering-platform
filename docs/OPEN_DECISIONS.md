# Open Business Decisions

These must be answered by the business before the dependent features are built. Engineering will not invent answers. Unrelated infrastructure work continues meanwhile.

Format: **Question** · *Why it matters* · **Blocks**

| # | Topic | Question | Why it matters | Blocks |
|---|---|---|---|---|
| 2 | Payment & deposit | Is any deposit or payment collected in-app? | Payments are out of scope unless approved | Nothing in MVP unless approved |
| 6 | Quote modification & negotiation | Can the owner edit or counter-propose a quote, or only approve/reject? | Adds states and UI | Out of MVP until decided |
| 7 | Cancellation & revision | Can a customer cancel or edit after submission or approval? Deadlines? | Adds states and rules | Out of MVP until decided |
| 9 | Kashrut certification | Which certification(s)? Shown per dish or business-wide? Mixing meat & dairy dishes in one order allowed? | Affects data model and validation | Phase 2 dish fields, Phase 3 conflict checks |
| 10 | Disposable serving equipment | Are utensils/disposables orderable? Priced how? | Could be catalog items or separate | Out of MVP until decided |
| 11 | Alcohol | Offered at all? Age verification? | Legal implications | Out of MVP until decided |

## Decision log

When a decision is made, record it here and move the row out of the table above.

| Date | # | Decision | Decided by |
|---|---|---|---|
| 2026-10-29 | 12 | Interface languages: Arabic, Hebrew and English; RTL for ar/he | Owner |
| 2026-10-29 | 13 | No notifications; quote requests are viewed on the admin page | Owner |
| 2026-10-29 | 17 | ILS (₪) | Owner |
| 2026-10-29 | 1 | Guest checkout, no accounts: customer leaves name + email or phone and gets a private link (token in the URL fragment). Provisional; can move to Supabase Auth later | Owner |
| 2026-10-29 | 3 | Mechanism only: owner sets per-category rules (per adult, per child, round-up step) in admin; no rule → no suggestion. Values not yet entered. Even split across selected dishes in a category is an engineering call | Owner |
| 2026-10-29 | 4 | Vegetarian/vegan/restricted guests are counted within adults + children (each ≤ total). They don't change quantities yet | Owner |
| 2026-10-29 | 14 | Catalog prices include VAT; no VAT line. Lines rounded half-up to 0.01 | Owner |
| 2026-10-29 | 5 | Lead time: events need at least 7 days' notice. No daily capacity cap; the owner rejects requests they can't take | Owner |
| 2026-10-29 | 9 | Mixing meat and dairy dishes in one order: warn the customer, don't block. (Certification display still open) | Owner |
| 2026-10-29 | 15 | Minimum order: ₪500 of food (delivery fee excluded) before a quote can be submitted | Owner |
| 2026-10-29 | 8 | Allergen disclaimer: "Our kitchen handles nuts, gluten, milk, eggs, sesame and more. We can't guarantee any dish is allergen-free. Contact us about severe allergies." No "may contain" level | Owner |
| 2026-10-29 | 19 | Delivery fee by distance: ₪50 base + ₪4/km from the kitchen (starting point Jerusalem until an exact address is set), max 40 km; geocoding via free OpenStreetMap; values editable in admin | Owner |
| 2026-10-29 | 16 | AI assistant (Phase 4): Anthropic Claude, no hard budget cap; track cost | Owner |
| 2026-10-29 | 18 | Weight unit: price per kg | Owner |
| 2026-10-29 | 20 | Business name: CaterKing (logo, colors: Stitch "Haute Epicure" style; logo still open) | Owner |
| 2026-10-30 | — | Hosting: Render (web, from `render.yaml`) + Supabase (Postgres, Auth, Storage) instead of Railway. Render was already connected to GitHub; Render's free Postgres expires after 30 days, and Supabase is needed for Auth/Storage anyway | Owner ("use what's better and more efficient") |
