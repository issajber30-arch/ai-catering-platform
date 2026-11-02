# Asset Manifest: yumm.ai illustrations (Green Eggs and Ham option)

Status: **Phase C.** The supplied V3 pack proved unusable for most categories (25 of 39 files were clipped at the source, see "History"), so the illustrations used by the app were regenerated and live in `frontend/assets/`. Originals are kept outside the repository (git-ignored): the V3 pack in `_brief/assets/v3/`, its cleaned subset in `_brief/assets/v3-clean/`, and the full-size generated sheets in `_brief/assets/generated-originals/`.

## Provenance

- **Tool and date:** OpenArt, GPT Image 2 (image-to-image), 2026-10-31, using the project owner's account.
- **Style references supplied to the model:** the cleaned V3 mascot pose and the V3 Shabbat scene, so the new art matches the character and line style the client chose. Prompts describe a "hand-inked picture-book style" and name no artist, book or character.
- **Processing:** background removed by flood-fill from the border, pale sticker rim stripped, sheets sliced into single items, trimmed with an 8 px margin, resized, exported as PNG and WebP (lossy WebP quality 90 with full alpha). Source art was not hand-edited.
- **Rights:** generated content, covered by the tool's terms; no third-party assets were added. Not reviewed by a human for resemblance to existing characters.
- **Originality review:** see the Mascot section.

## Mascot (`assets/mascot/<state>/`)

| File | State and use | Size (px) | PNG / WebP |
|---|---|---|---|
| `welcome/mascot-welcome` | Landing hero; event step greeting; assistant header, button and first message | 692x900 | 477 / 126 KB |
| `thinking/mascot-thinking` | Assistant avatar while it is replying | 541x900 | 477 / 122 KB |
| `suggesting/mascot-suggesting` | Assistant avatar on messages that carry a proposal; landing assistant intro | 453x900 | 414 / 114 KB |
| `explaining/mascot-explaining` | Assistant avatar on answers that carry no proposal (price, quantities, allergens) | 560x900 | 460 / 122 KB |
| `celebrating/mascot-celebrating` | Acknowledges the "request sent" moment and an approved assistant change; never shown for a pending proposal, an approved or rejected quotation | 654x900 | 538 / 148 KB |

**Originality review: uncleared.** The character is a stand-in. It was generated from the V3 mascot, which the pack README says may resemble familiar storybook characters, and no human has reviewed it. Keep it out of any pushed branch until reviewed or replaced. The project owner chose to use it for a course assignment.

## Occasions (`assets/occasions/`), 900 px wide

| File | Event type shown to the customer | Size (px) | PNG / WebP |
|---|---|---|---|
| `occasion-birthday` | יום הולדת | 900x695 | 820 / 187 KB |
| `occasion-family-dinner` | אירוע משפחתי | 900x721 | 929 / 213 KB |
| `occasion-bar-bat-mitzvah` | בר או בת מצווה (neutral: tiered cake with star, no flag or scroll) | 900x657 | 722 / 210 KB |
| `occasion-shabbat` | ארוחת שבת | 900x734 | 721 / 188 KB |
| `occasion-anniversary` | יום נישואין (added; the brief lists it) | 900x611 | 688 / 171 KB |
| `occasion-celebration` | חגיגה פרטית | 900x834 | 616 / 173 KB |
| `occasion-other` | אחר | 900x859 | 1022 / 255 KB |
| `occasion-garden-party` | Not an event type; available for hero or section use | 900x642 | 933 / 212 KB |

## Menu categories (`assets/menu-categories/`)

Category headers and chips only. Never used as a dish photo. `food-main` 800x473 (generated in Phase D for the mains category, 664 / 156 KB), `food-bread` 753x663, `food-canapes` 707x553, `food-dessert` 704x588, `food-fish` 782x525, `food-lemonade` 559x727, `food-salad` 795x689, `food-sides` 743x634 (118 to 170 KB each as WebP).

## Illustrated icons (`assets/icons/illustrated/`), 384 px wide, regenerated in a wonkier storybook style (lopsided blob badges, swirls, dots, stripes)

`icon-calendar`, `icon-guests`, `icon-location`, `icon-delivery`, `icon-serving`, `icon-fish`, `icon-gluten-free`, `icon-dairy-free`, `icon-nut-free`, `icon-vegan`, `icon-vegetarian` (24 to 43 KB as WebP). The dietary icons are labels only and must never stand in for verified dish data. The UI glyphs are now hand-inked masks (`assets/icons/hand/*.png`, 128 px, 21 files of 2 to 5 KB, generated as black ink on white and converted to transparency so CSS can colour them). The old Phosphor line icons (`assets/icons/*.svg`) are no longer referenced. Originals: `icons-sheet-v1.png`, `icons-sheet-v2.png`, `glyphs-sheet.png` in `_brief/assets/generated-originals/`.

## Decorations (`assets/decorations/`), up to 480 px

`decor-awning`, `decor-confetti`, `decor-lemon`, `decor-olives`, `decor-parsley`, `decor-rosemary`, `decor-tomatoes`, plus `decor-flourish` and `decor-leaf` generated but not yet used (37 to 70 KB as WebP).

## Totals and optimization

80 files (40 images, each as PNG and WebP): about 17.3 MB PNG and 4.0 MB WebP. The app serves WebP through `<picture>` with PNG fallback, sets width and height on every image, and lazy-loads everything below the fold. A later pass can quantize the PNG fallbacks or drop them.

## History

The supplied pack (`Catering_Mascot_Asset_Pack_V3.zip`, 39 PNGs) was audited and cleaned first. 14 files were rescued; 25 were clipped at the source (food sliced across the top, icon badges cut flat, decorations mixed and mislabeled). On the project owner's approval the missing and clipped pieces were regenerated at higher resolution, and the remaining mascot poses and occasion scenes were regenerated for one consistent style and resolution. The V3 files are no longer used by the app.

### Style pass 3: "nonsense picture-book" (2026-10-31)

On the project owner's request ("recreate the images to be more in Dr Seuss's style"), the occasions, menu categories, illustrated icons and decorations were regenerated again: curvy, drooping and lopsided shapes, spindly wavy outlines, loopy swirls, flat fills printed slightly off the ink lines, palette of red, aqua, yellow, pink and green. Prompts described these qualities only; no artist, book or character was named, and the output stays inside the client's originality rule. The mascot was deliberately left unchanged (already the closest to existing characters). Style reference given to the generator: the mascot only.

- Tool: OpenArt `gpt-image-2`, 4K sheets (food 4x2, decorations 5+4, icons 11, occasions as two 2x2 sheets), cut out with `process_assets.py` (valley-based grid split so neighbours never leak in).
- Originals: `_brief/assets/generated-originals/` (`food2-sheet`, `occA-sheet`, `occB-sheet`, `decor2-sheet`, `icons2-sheet`).
- Previous generation (pass 2) kept for rollback in `_brief/assets/style-v2-backup/`.
- `decor-flourish` and `decor-leaf` are still unused.
