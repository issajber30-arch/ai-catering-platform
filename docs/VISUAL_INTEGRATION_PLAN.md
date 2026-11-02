# Visual Integration Plan: Green Eggs and Ham option

Status: **Phase A approved with decisions (section 10); Phase A2 asset cleanup done.** No application code has been changed. Branch: `design/green-eggs-and-ham`.
Source brief: the client prompt for this option (V3 asset pack). Asset audit date: 2026-10-31.

## 1. Existing frontend (starting point)

Plain HTML, CSS and vanilla JS ES modules served statically by FastAPI (ADR-0001). No build step, no framework.

- `frontend/customer/index.html` boots `js/customer/main.js`, which mounts four views (`event`, `menu`, `summary`, `status`) and an assistant panel. Routing is the URL hash.
- State is a small store (`js/customer/store.js`) that bumps `order.version` on every mutation. It currently runs on a **mock backend** (`js/customer/mock-backend.js`) that mirrors `docs/API_CONTRACTS.md`. Pricing, quantity rules and assistant replies there are placeholders, not business rules.
- Styling: tokens and primitives in `css/base.css`, layout in `css/customer.css`, icons as vendored Phosphor SVG masks, Heebo self-hosted. Hebrew only, RTL, logical CSS properties.
- The admin page is a placeholder. Dish cards render an image only when the data supplies `image`; there is no business photography yet.

All redesign work should stay inside CSS, markup and presentational JS. The store, the mock backend and the approval flow are not touched.

## 2. V3 asset audit

Source: `Catering_Mascot_Asset_Pack_V3.zip` (2.3 MB, 41 entries, no unsafe paths). The `new assets` folder supplied alongside it is byte-identical (41 of 41 SHA-256 matches). Local copy: `_brief/assets/v3/` (git-ignored).

| Category | Expected | Found | Verified |
|---|---|---|---|
| Mascot poses | 5 | 5 | welcome, thinking, suggesting, explaining, celebrating |
| Occasions | 6 | 6 | birthday, celebration, family_dinner, garden_party, mitzvah, shabbat |
| Food | 7 | 7 | bread, canapes, dessert, fish, lemonade, salad, sides |
| Icons | 11 | 11 | calendar, dairy, delivery, fish, gluten, guests, location, nuts, serving, vegan, vegetarian |
| Decorations | 10 | 10 | awning, chef_hat, chili, heart, herbs, leaf, lemon, olives, swirl, tomatoes |
| Manifest | 1 | 1 | 39 entries, matches the 39 PNGs on disk |
| README | 1 | 1 | **says "38 images"; there are 39** |

Technical facts: all 39 are 512x512 RGBA PNGs with real transparency (the artwork covers 0.5% to 19% of the canvas). 14 to 182 KB each. No byte-identical duplicates. No file touches the canvas edge.

## 3. Concerns

**Originality (blocking for commercial use).** The V3 creature is a yellow, furry, whiskered character with a long nose, hand-inked in a classic picture-book style. It closely echoes existing Dr. Seuss character design, including the yellow character in Green Eggs and Ham, even though the striped hat from the earlier pack is gone. The pack README itself says it "may still resemble familiar storybook characters". This audit cannot clear it. Treat the mascot as concept art until a human originality or legal review, or a redraw, clears it.

**Cropping and fragments (blocking for production).** The images were cut from a sprite sheet with crop boxes that are too loose. Every category contains slivers or cut-off pieces of neighbouring sprites, with hard straight edges:

| Category | Problem |
|---|---|
| Mascots | Small stray marks: welcome (right crescent), thinking (left fragment), suggesting (right fragment), celebrating (left dot). Easy to erase. |
| Occasions | All six include cut-off neighbouring objects (greens, bread, utensils, balloons, chairs) along the bottom and sides. Needs cleanup or regeneration. |
| Food | All seven have a flat lower edge with fragments of icon backing circles beneath. |
| Icons | Most have side slivers, and several backing circles are clipped flat (location, serving, vegan). |
| Decorations | See below. |

**Decoration filenames do not match contents, and one is duplicated.**

| File | Actually contains |
|---|---|
| `decor_chili` | parsley sprig plus a swirl fragment (no chili) |
| `decor_leaf` | a black swirl flourish (no leaf) |
| `decor_lemon` | lemon wedge plus olives |
| `decor_olives` | a red chili pepper plus fragments |
| `decor_swirl` | a red-and-white awning (a second awning) |
| `decor_herbs` | herb sprig plus a tomato |
| `decor_tomatoes` | tomatoes plus a lemon slice |

Clean: `decor_chef_hat`, `decor_heart` (minor right-edge fragment), `decor_awning` (clipped on the left).

**Resolution.** The artwork is small inside its canvas: mascots about 200-270 x 320-336 px, food about 160-210 x 144, icons about 100 x 96, decorations 30-145 px wide. A hero mascot above about 330 CSS px will look soft, and retina screens halve that. Icons are fine up to about 48 CSS px.

**State fit.** `mascot_explaining` shows the character presenting a covered dish. It reads as "serving", not "explaining a proposed change". `mascot_suggesting` (pointing, lightbulb) fits both "suggesting" and "explaining".

**Other.** The dietary icons are illustrations only and must never stand in for verified dish data (the README says the same). The mitzvah scene shows a Torah scroll draped with an Israeli flag; confirm with the client that this is wanted. The manifest has no fields for intended use, optimization status or originality review, all of which the brief requires.

**Production readiness:** none of the 39 assets is production-ready as supplied.

## 4. Proposed visual direction

"Storybook kitchen", adult-appropriate: warm cream paper ground, bold ink outlines, deep-green structure, red and butter-yellow accents used sparingly. The illustrated universe lives in the hero, occasion picker, category headers, empty states, and the assistant. Ordering surfaces (forms, dish cards, summary, quote status) stay calm and typographic. The mascot appears as the assistant's identity and in a few welcome and success moments, never inside form fields or the price summary.

## 5. Asset-to-screen map

| Screen | Assets | Rule |
|---|---|---|
| Landing (new) | `mascot_welcome`, 3 to 4 occasions, `decor_chef_hat`, `decor_heart` | Hero is a clean composition built from cleaned assets, not a raw sprite crop |
| Event details (C1) | 6 occasion illustrations as selectable event-type cards; `icon_calendar`, `icon_guests`, `icon_delivery`, `icon_location` | Form stays plain; illustrations are decorative (`alt=""`); every card is a real radio |
| Menu (C2) | 7 food illustrations as category headers or chips; `icon_nuts`, `icon_gluten`, `icon_dairy`, `icon_fish`, `icon_vegan`, `icon_vegetarian` only as labels beside backend data | Dish cards use business photos when they exist, never these illustrations |
| Summary (C3) | none, or one `decor_heart` | Minimal by design |
| Assistant (C4) | `mascot_thinking` (processing), `mascot_suggesting` (recommendations), `mascot_explaining` (proposal card, pending the state-fit decision), `mascot_welcome` (first open) | The approve and reject buttons carry no mascot or animation |
| Submission and status (C5) | `mascot_celebrating` only for "request sent". Pending shows the clock badge. Approved shows a seal. Rejected shows no celebration | Never celebrate an unapproved quote |
| Admin | none (colors and type only) | |

## 6. Missing artwork

- A cleaned, higher-resolution mascot set (target 1024 px on the long side) and a mascot for the empty-order state.
- Clean occasion illustrations. Missing from the supplied set: **anniversary**, which the brief lists as an occasion, and a generic "other occasion".
- A logo or wordmark (business name is still undecided, open decision #20).
- A hero background composition, a favicon, and an Open Graph image.
- Real dish photography for the catalog (business-supplied).
- Menu-category art for any category beyond the seven food illustrations (for example drinks beyond lemonade, mains).

## 7. Proposed design system

Tokens (semantic names; palette from the brief; contrast measured with the WCAG formula):

```css
:root {
  --color-bg: #FFF9ED;          --color-surface: #FFFFFF;
  --color-ink: #202020;         --color-ink-muted: #4A4A44;
  --color-primary: #3F702B;     /* deep green: buttons, links, focus */
  --color-primary-fill: #82B441;/* brand green: fills and illustration only, ink text on top */
  --color-accent: #F0442D;      /* decorative and large type only */
  --color-accent-text: #C2321F; /* derived darker red for small text and badges */
  --color-highlight: #FFD65A;
  --focus-ring: 3px solid var(--color-primary);
  --radius-sm: 12px; --radius-md: 20px; --radius-pill: 999px;
}
```

| Pair | Ratio | Verdict |
|---|---|---|
| ink on bg | 15.5 | pass |
| deep green on bg | 5.6 | pass (body text and links) |
| white on deep green | 5.9 | pass (primary button) |
| ink on brand green | 6.6 | pass (green fills with dark text) |
| **white on brand green** | **2.5** | **fail: do not use** |
| **red on bg** | **3.6** | **fail for small text; large type only** |
| white on red | 3.8 | large text only |
| derived red `#C2321F` on bg | 5.3 | pass (badges, errors, small text) |
| ink on butter yellow | 11.7 | pass |

So the brief's brand green and red cannot carry small text as specified. The proposal keeps both for fills and illustration and adds a darker text-safe red.

Typography (self-hosted, no external font host): display options with Hebrew coverage are **Secular One** (chunky, friendly), **Playpen Sans Hebrew** (hand-lettered), or **Suez One** (display serif). Interface stays **Heebo** (already self-hosted) or Assistant. Display is for headlines only; prices, labels and chat use the interface face.

Imagery: trim each asset to its artwork, export WebP with PNG originals retained under `assets/_originals/`, fixed `width` and `height` attributes, `loading="lazy"` below the fold, `srcset` at 1x and 2x for the mascot. Motion: none until the static design is approved; later a single entrance and a subtle thinking bob, both disabled under `prefers-reduced-motion`.

## 8. Incremental plan

| Phase | Scope | Stop condition |
|---|---|---|
| A (this document) | Audit and proposal | Approval of the decisions below |
| A2 (needs approval) | Clean the assets: erase fragments, trim, fix filenames, add the missing manifest fields, create `docs/ASSET_MANIFEST.md` | Review of the cleaned set |
| B | Tokens, typography, shared components in CSS. `docs/VISUAL_IDENTITY.md` | Review |
| C | Landing page and event details | Mobile and accessibility check, then review |
| D | Menu and assistant, five mascot states | Approval flow verified unchanged, then review |
| E | QA: layouts, transparency, loading, keyboard, readability, AI proposal controls, quote status, existing tests | Final review |

Every phase ends on the `design/green-eggs-and-ham` branch with nothing pushed until you say so. `main` is never touched.

## 9. Decisions needed

1. Originality: proceed with the V3 mascot as concept art only, or commission a redraw first?
2. Asset cleanup: may I clean the pack (erase fragments, trim, rename mismatched decorations), or do you want regenerated sources?
3. Palette: accept the darker text-safe red and the deep green for buttons, with the brand green for fills only?
4. Display font: Secular One, Playpen Sans Hebrew or Suez One?
5. Add a landing page (the app currently opens straight into event details)?
6. Mascot state for "explaining": reuse the suggesting pose, or request a new one?
7. Mitzvah illustration with the flag and Torah scroll: keep, or replace?
8. Name and logo (open decision #20): placeholder wordmark for now?

## 10. Decisions recorded (2026-10-31)

| # | Decision | Status |
|---|---|---|
| 1 | Mascot originality | **Project owner: use this mascot (course assignment).** Still uncleared by any human review; the repository and fork are public, so pushing the mascot files remains the owner's call. |
| 2 | Clean the pack | **Approved and done.** See `docs/ASSET_MANIFEST.md`. 14 of 39 files rescued; 25 are clipped at the source and need redrawing. |
| 3 | Palette adjustments (deep-green buttons, brand green for fills, derived text-safe red) | **Approved.** |
| 4 | Display font | **Playpen Sans Hebrew ExtraBold** (chosen by the project owner). |
| 5 | Add a landing page | **Approved.** |
| 6 | "Explaining" pose | **Superseded:** a proper explaining pose (holding a blank notepad) was generated, so no stand-in is needed. |
| 7 | Mitzvah illustration | **Done:** replaced with a neutral tiered-cake celebration (no flag, no scroll). |
| 8 | Business name | **yumm.ai.** Latin wordmark, set LTR inside RTL layouts. Logo still to be designed. |

## 11. Phase A2 result

The cleaning pass rescued 14 of 39 files. 10 are usable as is, 4 carry a clipped edge, and 25 (all food, all icons, 7 decorations) are cut off in the source and need redrawing, which cleanup cannot fix. Details and per-file status are in `docs/ASSET_MANIFEST.md`.

Consequence for the plan: Phase C can proceed with the 5 mascots, the occasions (with the caveats above) and typography, using Phosphor icons for UI glyphs. Phase D's food category art is blocked on a redraw or approved regeneration, so category headers stay typographic in the meantime.

## 12. Phase B result (design system)

Implemented: semantic colour, type, shape, depth, focus, motion and layout tokens in `css/base.css`; Playpen Sans Hebrew ExtraBold self-hosted as a static 87 KB pair; the `yumm.ai` wordmark; restyled buttons, fields, badges, chips, cards and panels across the existing customer screens; `docs/VISUAL_IDENTITY.md` with the visual QA checklist.

Verified: renders on desktop and 390 px phone, no horizontal overflow on the event, menu and summary steps, assistant panel and approve/reject controls intact, fonts loaded from the project. The existing ordering code is unchanged (CSS, markup and the page title only). The automated Python tests were not run: `uv` is not installed on this machine and no backend code changed.

Known gaps: the landing page and admin placeholder still use the old styling (Phase C); no illustrations are in the UI yet.

## 13. Image generation (approved 2026-10-31)

The project owner approved generating the missing artwork and said there would be no real dish photos, so all imagery is generated. 7 food, 11 icons, 9 decorations, 8 occasion scenes and 5 mascot poses were generated with OpenArt (GPT Image 2) in a hand-inked picture-book style, using the V3 mascot and Shabbat scene as style references and no artist or character names in the prompts. About 650 credits were used of 5,866. Details and provenance: `docs/ASSET_MANIFEST.md`.

Note for Phase D: because no business photography will exist, the client brief's rule that dish cards use real photos cannot be met. Dish cards show no image unless the data supplies one; the food illustrations are used as category headers only and must not be presented as the dishes being sold.

## 14. Phase C result (landing and event setup)

Built: the landing page, the illustrated occasion picker with `?occasion=` preselection, the welcome mascot on the event step, the illustration helper, WebP delivery with reserved dimensions. Verified on desktop and a 390 px phone: no horizontal overflow, occasion preselection works, the event flow is unchanged. Two defects found and fixed during review: a double page gutter from the generic `main` padding, and a legibility problem with the display face at small sizes (now restricted to 32 px and up).

Not done yet (Phase D): the five mascot states in the assistant, food category headers in the menu, the celebrating mascot on the "request sent" status, the quote-status presentation check. Phase E: full QA and the Python tests (`uv` is not installed here).

## 15. Phase D result (catalog and assistant)

Built: category drawings in the menu headers and chips; the mascot as the assistant's identity with all five states wired to real moments; the celebrating mascot on the "request sent" screen; one extra generated image (`food-main`, a roast chicken dish) for the mains category. Verified in the browser on desktop and a 390 px phone: the states switch correctly (thinking while replying, suggesting on a proposal, celebrating only after approval), the approve and reject flow and price differences are unchanged, no horizontal overflow, the pending status screen carries the plain-text pending message. The data layer (store, mock backend, pricing, approval flow) was not touched.

Phase E (done, section 17) covered: full QA pass (keyboard, reduced motion, readability, image-off check), the automated Python tests (`uv` is not installed here), the final checklist in `docs/VISUAL_IDENTITY.md`, and an owner decision on whether the mascot files may be pushed to the public fork.

## 16. Motion layer (requested by the project owner)

The client brief held animation back until the static design was approved; the owner then asked for more dynamic features, which was taken as that approval. Added within the brief's limits (subtle, meaningful, no continuous distraction): landing arrival and scroll reveals, pointer drift on the hero art, a clickable approval example, step transitions, add-to-order feedback, live totals that count, assistant message and thinking states, and two confetti moments (an approved change; "request sent"). All of it respects `prefers-reduced-motion`. Details and the accessibility handling are in `docs/VISUAL_IDENTITY.md` ("Motion layer"). No data layer or business logic changed.

Verified in the browser: hero and step animations run, the landing example approves and resets, the card bump, new sidebar line, thinking wobble, new-message animation and confetti all fire on the right events, and animated totals end on the exact value. Not verified: a real reduced-motion run (the browser tool cannot set the preference); that path relies on the `matchMedia` guard plus the base stylesheet's global override.

## 17. Phase E result (final integration and QA)

**Automated tests.** Backend: `pytest` 2 passed (`tests/test_health.py`), `ruff check` clean, run in a throwaway virtual environment outside the repository because `uv` is not installed. The backend was not changed on this branch. The frontend has no automated tests in the repository; it was checked in the browser instead (below). The design detector reports one finding per page (cream background, a palette the client specified) and seven advisory notes about the spring easing used for small playful moments; both are accepted deliberately.

**Layouts.** Landing, event, menu and summary were audited at 320, 390, 768 and desktop widths (narrow widths in same-origin frames, because the browser tool cannot resize the viewport). No horizontal overflow, no broken images, every image has `alt` and reserved dimensions, every control has an accessible name and every field a label. The status screen was checked at desktop width only.

**Fixed during QA.**
1. At 320 px the step indicator pushed the header 37 px wider than the screen. The current step's label is now visually hidden at 360 px and below (the page title names the step).
2. On phones the labels of non-current steps were removed with `display:none`, which left the step buttons with only a number or a checkmark as their name for screen readers. They are now visually hidden instead, so the names stay in the accessibility tree.
3. The footer link "ממשק העסק" was 22 px tall (below the 24 px minimum target size); it is now 44 px.
4. Scene cutouts could keep a stray fragment of the neighbouring picture; small leftovers are now dropped.

**Keyboard.** With real Tab presses on the event step: the skip link comes first, then the wordmark link, the occasion group (one tab stop, arrow keys inside), date, time, and each guest counter. Every stop shows the 2.4 px focus ring and stays in view. Validation errors are inline with an icon and move focus to the first invalid field.

**Ordering flow, end to end** (event, menu, add dishes, ask the assistant, reject, ask again, approve, summary, empty-form validation, submit, status), against the mock backend: reject leaves the order unchanged and marks the card as rejected; approve applies the change and the totals add up (85 + 80 + 296 = 461 ₪); the status screen says the request is pending business approval and is not a confirmed order. Pricing, store and approval code were not touched.

**Reduced motion.** The preference cannot be set from the browser tool, so the reduce rules were forced on in a test: no element kept an animation or transition and all 13 reveal blocks were visible. All script-driven effects (hero drift, count-up totals, confetti, reveals) are guarded by `reduced()`.

**Images off.** With every `<img>` hidden, the landing page and the event step remain fully usable: each choice keeps its text label.

**Not done / limits.** No real screen reader or real phone test; contrast was verified when the tokens were set (Phase B) and not re-measured; the Hebrew copy has not had a native-speaker proofread; the interactive-table option, pushing to GitHub, and the mascot-licensing question remain owner decisions.
