import { fill, h, icon } from "../../lib/dom.js";
import { fmtMoney, fmtNumber } from "../../lib/format.js";
import { play } from "../../lib/motion.js";
import { qtyLabel, recommendedQty, unitStep, totalGuests } from "../mock-backend.js";
import { showAllergenInfo } from "./allergen-dialog.js";

const PER_UNIT = { tray: "למגש", kg: "לק״ג", item: "ליחידה", guest: "לאורח" };
const KASHRUT = { meat: ["בשרי", "badge-meat"], dairy: ["חלבי", "badge-dairy"], pareve: ["פרווה", "badge-pareve"] };

export function dietaryBadges(dish) {
  const out = [];
  if (dish.kashrut && KASHRUT[dish.kashrut]) out.push(h("span", { class: `badge ${KASHRUT[dish.kashrut][1]}`, text: KASHRUT[dish.kashrut][0] }));
  if (dish.vegan) out.push(h("span", { class: "badge badge-green" }, icon("leaf"), "טבעוני"));
  else if (dish.vegetarian) out.push(h("span", { class: "badge badge-green" }, icon("leaf"), "צמחוני"));
  return out;
}

/**
 * Dish card. Built once; update(qty, event) patches only the quantity area so keyboard focus
 * on the +/- buttons survives every change.
 */
export function createDishCard(dish, { onQty }) {
  const qtyArea = h("div", { class: "dish-qty" });
  const name = h("h3", { class: "dish-name", text: dish.name });

  const el = h("article", { class: "dish-card", "aria-label": dish.name },
    dish.image ? h("img", { class: "dish-image", src: dish.image, alt: "", loading: "lazy" }) : null,
    h("div", { class: "dish-head" },
      name,
      h("p", { class: "dish-price" },
        h("strong", { text: fmtMoney(dish.price) }),
        h("span", { class: "muted", text: ` ${PER_UNIT[dish.unit]}` })),
    ),
    h("p", { class: "dish-desc muted", text: dish.description }),
    h("div", { class: "badge-row" }, dietaryBadges(dish)),
    h("button", { class: "link-btn", type: "button", onclick: () => showAllergenInfo(dish) }, icon("info"), "מידע על אלרגנים"),
    qtyArea,
  );

  let lastQty = null;
  function update(qty, event) {
    const step = unitStep(dish);
    const rec = recommendedQty(dish, event);
    const hasGuests = totalGuests(event) > 0;
    el.classList.toggle("in-order", qty > 0);
    // Feedback when a dish is added or increased (not on the first render or on a decrease).
    if (lastQty !== null && qty > lastQty) play(el, "bump");
    lastQty = qty;

    const focusedKey = qtyArea.contains(document.activeElement) ? document.activeElement.dataset.key : null;

    if (qty <= 0) {
      fill(qtyArea, 
        h("button", { class: "btn btn-secondary", type: "button", "data-key": "add", onclick: () => onQty(dish.id, step) },
          icon("plus"), "הוספה"),
        hasGuests ? h("button", { class: "link-btn", type: "button", "data-key": "rec", onclick: () => onQty(dish.id, rec) },
          `הוסיפו כמות מומלצת: ${qtyLabel(dish, rec)}`) : null,
      );
    } else {
      fill(qtyArea, 
        h("div", { class: "qty-stepper" },
          h("button", { class: "btn btn-secondary btn-icon", type: "button", "data-key": "minus",
            "aria-label": `הפחתת כמות: ${dish.name}`, onclick: () => onQty(dish.id, Math.max(0, +(qty - step).toFixed(2))) },
            icon(qty - step <= 0 ? "trash" : "minus")),
          h("span", { class: "qty-value", role: "status", "aria-label": `${dish.name}: ${qtyLabel(dish, qty)}`, text: qtyLabel(dish, qty) }),
          h("button", { class: "btn btn-secondary btn-icon", type: "button", "data-key": "plus",
            "aria-label": `הוספת כמות: ${dish.name}`, onclick: () => onQty(dish.id, +(qty + step).toFixed(2)) },
            icon("plus")),
        ),
        hasGuests && qty !== rec ? h("p", { class: "muted small", text: `מומלץ ל-${fmtNumber(totalGuests(event))} אורחים: ${qtyLabel(dish, rec)}` }) : null,
      );
    }
    // Keep keyboard focus on the same control; when it disappears (add -> stepper, last remove -> add)
    // fall back to the control that replaced it.
    if (focusedKey) {
      (qtyArea.querySelector(`[data-key="${focusedKey}"]`) ?? qtyArea.querySelector('[data-key="plus"], [data-key="add"]'))?.focus();
    }
  }

  return { el, update };
}
