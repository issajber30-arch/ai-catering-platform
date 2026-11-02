// C2: dish catalog with a live order sidebar.
import { fill, h, icon } from "../../lib/dom.js";
import { announce } from "../../lib/announce.js";
import { fmtDate, fmtMoney, fmtNumber } from "../../lib/format.js";
import { CATEGORIES, DISHES, priceOrder, qtyLabel, totalGuests } from "../mock-backend.js";
import { CATEGORY_ART, illustration } from "../../lib/illustrations.js";
import { animatedAmount } from "../../lib/motion.js";
import { createDishCard } from "../components/dish-card.js";
import { getState, goto, setQty, subscribe } from "../store.js";

// Stand-in for GET /api/catalog/categories and /dishes. The delay lets the skeleton state be reviewed.
function loadCatalog() {
  return new Promise((resolve) => setTimeout(() => resolve({ categories: CATEGORIES, dishes: DISHES }), 350));
}

export function mountMenu(root) {
  let catalog = null;
  let activeCategory = "all";
  const diet = { vegetarian: false, vegan: false };
  const cards = new Map();
  let lastItems = null;
  let lastTotal = null;

  const chips = h("div", { class: "chip-row scroll-x", role: "group", "aria-label": "קטגוריות" });
  const filters = h("div", { class: "chip-row", role: "group", "aria-label": "סינון תזונתי" });
  const catalogEl = h("div", { class: "catalog", "aria-busy": "true" });
  const sidebar = h("aside", { class: "order-side", "aria-label": "ההזמנה שלכם" });
  const bar = h("div", { class: "bottom-bar" });

  const e0 = getState().order.event;
  fill(root, 
    h("h1", { class: "page-title", text: "בחרו מנות לתפריט" }),
    h("p", { class: "page-lead muted", text: `${e0.type}, ${fmtDate(e0.date)}, ${fmtNumber(totalGuests(e0))} אורחים` }),
    h("div", { class: "menu-layout" },
      h("div", { class: "menu-main stack-lg" }, h("div", { class: "stack" }, chips, filters), catalogEl),
      sidebar,
    ),
    bar,
  );
  document.body.classList.add("has-bottom-bar");

  /* ----- filter controls ----- */
  function chip(label, pressed, onClick, art) {
    // The drawing is decorative; the label is the accessible name.
    return h("button", { class: "chip", type: "button", "data-key": label, "aria-pressed": String(pressed), onclick: onClick },
      art ? illustration(art, { alt: "", cls: "chip-art" }) : null, label);
  }

  function renderControls() {
    const focusKey = document.activeElement?.closest?.(".chip-row") && (chips.contains(document.activeElement) || filters.contains(document.activeElement))
      ? document.activeElement.dataset.key : null;
    fill(chips, 
      chip("הכל", activeCategory === "all", () => { activeCategory = "all"; renderCatalog(); renderControls(); }),
      catalog.categories.map((c) => chip(c.name, activeCategory === c.id, () => { activeCategory = c.id; renderCatalog(); renderControls(); }, CATEGORY_ART[c.id])),
    );
    fill(filters, 
      chip("צמחוני", diet.vegetarian, () => { diet.vegetarian = !diet.vegetarian; renderCatalog(); renderControls(); }),
      chip("טבעוני", diet.vegan, () => { diet.vegan = !diet.vegan; renderCatalog(); renderControls(); }),
    );
    if (focusKey) root.querySelector(`.chip[data-key="${focusKey}"]`)?.focus();
  }

  function visible(dish) {
    if (activeCategory !== "all" && dish.categoryId !== activeCategory) return false;
    if (diet.vegan && !dish.vegan) return false;
    if (diet.vegetarian && !(dish.vegetarian || dish.vegan)) return false;
    return true;
  }

  /* ----- catalog ----- */
  function ensureCard(dish) {
    if (!cards.has(dish.id)) {
      const card = createDishCard(dish, { onQty: setQty });
      cards.set(dish.id, card);
    }
    const card = cards.get(dish.id);
    card.update(getState().order.items[dish.id] ?? 0, getState().order.event);
    return card.el;
  }

  function renderCatalog() {
    const shown = catalog.dishes.filter(visible);
    catalogEl.setAttribute("aria-busy", "false");
    if (!shown.length) {
      fill(catalogEl, 
        h("div", { class: "empty" },
          h("p", { class: "empty-title", text: "אין מנות שמתאימות לסינון" }),
          h("p", { class: "muted", text: "נסו להסיר את הסינון התזונתי או לעבור לקטגוריה אחרת." }),
          h("button", { class: "btn btn-secondary", type: "button", onclick: () => {
            diet.vegetarian = diet.vegan = false; activeCategory = "all"; renderCatalog(); renderControls();
          } }, "ניקוי סינון")));
      return;
    }
    const groups = catalog.categories
      .map((c) => ({ c, dishes: shown.filter((d) => d.categoryId === c.id) }))
      .filter((g) => g.dishes.length);
    fill(catalogEl, 
      groups.map(({ c, dishes }) =>
        h("section", { class: "category", "aria-labelledby": `cat-${c.id}` },
          h("div", { class: "category-head" },
            CATEGORY_ART[c.id] ? illustration(CATEGORY_ART[c.id], { alt: "", cls: "category-art" }) : null,
            h("h2", { id: `cat-${c.id}`, class: "category-title", text: c.name })),
          h("div", { class: "dish-grid" }, dishes.map(ensureCard)))),
    );
    announce(`מוצגות ${shown.length} מנות`);
  }

  /* ----- order sidebar + mobile bar ----- */
  let seenLines = new Set(); // dish ids already shown in the sidebar, so only a newly added dish animates in
  function renderOrder(state) {
    const pricing = priceOrder(state.order);
    const count = pricing.lines.length;
    const ids = new Set(pricing.lines.map((l) => l.dish.id));
    const firstRender = lastTotal === null;
    fill(sidebar,
      h("h2", { class: "side-title" }, icon("shopping-bag-open"), "ההזמנה שלכם"),
      count
        ? h("ul", { class: "side-lines" }, pricing.lines.map((l) => h("li", { class: `side-line${!firstRender && !seenLines.has(l.dish.id) ? " is-new" : ""}` },
          h("span", { class: "side-name" }, h("span", { text: l.dish.name }), h("span", { class: "muted small", text: qtyLabel(l.dish, l.qty) })),
          h("span", { class: "num", text: fmtMoney(l.lineTotal) }))))
        : h("p", { class: "muted", text: "עדיין לא נבחרו מנות. הוסיפו מנות מהתפריט." }),
      h("div", { class: "side-total" },
        h("span", { text: "סכום ביניים" }),
        animatedAmount(pricing.subtotal, lastTotal, fmtMoney)),
      h("p", { class: "muted small", text: "דמי משלוח, אם יש, יתווספו בסיכום." }),
      h("button", { class: "btn btn-primary btn-block", type: "button", disabled: !count, onclick: () => goto("summary") },
        "לסיכום ההזמנה", icon("arrow-left")),
    );
    fill(bar, 
      h("div", { class: "bar-total" },
        h("span", { class: "muted small", text: count ? `${count} מנות בהזמנה` : "ההזמנה ריקה" }),
        animatedAmount(pricing.subtotal, lastTotal, fmtMoney)),
      h("button", { class: "btn btn-primary", type: "button", disabled: !count, onclick: () => goto("summary") }, "לסיכום", icon("arrow-left")),
    );
    if (lastTotal !== null && lastTotal !== pricing.subtotal) announce(`סכום ביניים ${fmtMoney(pricing.subtotal)}`);
    lastTotal = pricing.subtotal;
    seenLines = ids;
  }

  /* ----- boot ----- */
  fill(catalogEl, 
    h("div", { class: "dish-grid", "aria-hidden": "true" },
      Array.from({ length: 6 }, () => h("div", { class: "skeleton dish-skeleton" }))));

  function boot() {
    loadCatalog().then((data) => {
      catalog = data;
      renderControls();
      renderCatalog();
    }).catch(() => {
      catalogEl.setAttribute("aria-busy", "false");
      fill(catalogEl, 
        h("div", { class: "empty", role: "alert" },
          h("p", { class: "empty-title", text: "לא הצלחנו לטעון את התפריט" }),
          h("p", { class: "muted", text: "בדקו את החיבור ונסו שוב." }),
          h("button", { class: "btn btn-secondary", type: "button", onclick: boot }, "ניסיון חוזר")));
    });
  }
  boot();
  renderOrder(getState());

  const unsubscribe = subscribe((state) => {
    if (state.step !== "menu") return;
    if (state.order.items !== lastItems) {
      lastItems = state.order.items;
      if (catalog) {
        for (const [id, card] of cards) card.update(state.order.items[id] ?? 0, state.order.event);
      }
      renderOrder(state);
    }
  });
  lastItems = getState().order.items;

  return () => {
    unsubscribe();
    document.body.classList.remove("has-bottom-bar");
  };
}
