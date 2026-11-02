import { fill, h, icon } from "../../lib/dom.js";

let dialog;

// Disclaimer wording is a placeholder until OPEN_DECISIONS #8 is answered by the business.
const DISCLAIMER = "המידע מוזן על ידי העסק. במקרה של אלרגיה חמורה מומלץ לוודא ישירות מול העסק לפני האירוע.";

export function showAllergenInfo(dish) {
  if (!dialog) {
    dialog = h("dialog", { class: "dialog", "aria-labelledby": "allergen-title" });
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    document.body.append(dialog);
  }

  let body;
  if (dish.allergens === null) {
    body = h("p", { class: "callout callout-warning" }, icon("warning"),
      h("span", { text: "אין לעסק מידע על אלרגנים במנה הזו. אי אפשר להניח שהיא נקייה מאלרגנים." }));
  } else if (dish.allergens.length === 0) {
    body = h("p", { text: "לא סומנו אלרגנים נפוצים במנה הזו." });
  } else {
    body = h("div", {},
      h("p", { text: "המנה מכילה או עלולה להכיל:" }),
      h("ul", { class: "chip-list" }, dish.allergens.map((a) => h("li", { class: "badge badge-warning", text: a }))),
    );
  }

  fill(dialog, 
    h("div", { class: "dialog-body" },
      h("h2", { id: "allergen-title", class: "dialog-title", text: `מידע על אלרגנים: ${dish.name}` }),
      body,
      h("p", { class: "muted small", text: DISCLAIMER }),
      h("div", { class: "dialog-actions" },
        h("button", { class: "btn btn-primary", type: "button", onclick: () => dialog.close() }, "הבנתי"),
      ),
    ),
  );
  dialog.showModal();
}
